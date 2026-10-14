from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse
import uvicorn
from google import genai
from PIL import Image, ImageDraw
import io
import base64
import re
import hashlib
import sqlite3
from typing import Optional

app = FastAPI()

# Initialize Gemini Client
client = genai.Client(api_key="AQ.Ab8RN6JirfVnYawcnsylOEkRpgeE_Snoq2zyNKLGLeK3r-0iGQ")

# Initialize Local SQLite Cache & Inventory Database
def init_db():
    conn = sqlite3.connect('brick_scanner.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_cache (
            hash_key TEXT PRIMARY KEY,
            description TEXT,
            image_b64 TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_number TEXT,
            part_name TEXT,
            box_location TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>the brick scanner</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; background: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { width: 100%; max-width: 480px; background: #1e293b; padding: 20px; border-radius: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); box-sizing: border-box; }
        
        .header { display: flex; justify-content: space-between; align-items: center; background: #334155; padding: 10px 16px; border-radius: 30px; margin-bottom: 20px; }
        .header span { font-weight: 600; font-size: 16px; letter-spacing: 0.5px; color: #fff; }
        .circle-btn { width: 36px; height: 36px; border-radius: 50%; background: #475569; border: none; color: white; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; }

        .camera-screen { display: block; }
        .camera-screen.hidden { display: none; }

        .set-input-box { margin-bottom: 12px; }
        .set-input-box label { display: block; font-size: 13px; font-weight: 600; color: #94a3b8; margin-bottom: 6px; }
        .set-input { width: 100%; background: #0f172a; border: 2px solid #64748b; border-radius: 12px; padding: 12px; color: white; font-size: 16px; box-sizing: border-box; outline: none; transition: 0.2s; }
        .set-input:focus { border-color: #38bdf8; }

        .upload-row { display: flex; gap: 10px; margin-bottom: 12px; }
        .upload-card { flex: 1; border: 2px dashed #64748b; border-radius: 14px; padding: 12px 10px; background: #0f172a; text-align: center; cursor: pointer; transition: 0.2s; position: relative; overflow: hidden; }
        .upload-card:hover { border-color: #38bdf8; }
        .upload-card p { margin: 6px 0 0; color: #94a3b8; font-size: 12px; font-weight: 500; }
        
        .preview-thumb { width: 100%; height: 75px; object-fit: cover; border-radius: 8px; margin-top: 6px; display: none; }

        /* Quality Warnings */
        #qualityWarning { background: rgba(234, 179, 8, 0.15); border: 1px solid #eab308; color: #fde047; padding: 8px 12px; border-radius: 8px; font-size: 12px; margin-bottom: 12px; display: none; text-align: center; }

        .scan-main-btn { background: #2563eb; color: white; border: none; border-radius: 30px; padding: 16px; width: 100%; font-size: 18px; font-weight: 700; cursor: pointer; margin-top: 6px; transition: background 0.2s, transform 0.1s; letter-spacing: 1px; box-shadow: 0 4px 12px rgba(37,99,235,0.4); }
        .scan-main-btn:hover { background: #1d4ed8; }
        .scan-main-btn:active { transform: scale(0.98); }
        .scan-main-btn:disabled { background: #475569; box-shadow: none; cursor: not-allowed; }

        #result-container { display: none; text-align: center; position: relative; }
        #result-container.active { display: block; }

        .image-wrapper { position: relative; display: inline-block; max-width: 100%; margin-top: 8px; }
        #result-img { max-width: 100%; height: auto; border-radius: 12px; display: block; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }

        #correction-box {
            position: absolute;
            border: 3px dashed #38bdf8;
            background: rgba(56, 189, 248, 0.25);
            display: none;
            cursor: move;
            box-sizing: border-box;
            pointer-events: auto;
        }

        .handle {
            position: absolute;
            width: 14px;
            height: 14px;
            background: #38bdf8;
            border: 2px solid #fff;
            border-radius: 50%;
            pointer-events: auto;
        }
        .handle-tl { top: -8px; left: -8px; cursor: nwse-resize; }
        .handle-tr { top: -8px; right: -8px; cursor: nesw-resize; }
        .handle-bl { bottom: -8px; left: -8px; cursor: nesw-resize; }
        .handle-br { bottom: -8px; right: -8px; cursor: nwse-resize; }

        #description { margin-top: 8px; background: #0f172a; padding: 10px; border-radius: 12px; text-align: left; font-size: 13px; color: #e2e8f0; line-height: 1.4; white-space: pre-wrap; max-height: 110px; overflow-y: auto; }
        
        .storage-box-section { margin-top: 8px; display: flex; gap: 8px; }
        .storage-input { flex: 1; background: #0f172a; border: 1px solid #64748b; border-radius: 8px; padding: 8px; color: white; font-size: 13px; }
        .storage-btn { background: #059669; color: white; border: none; border-radius: 8px; padding: 8px 14px; font-weight: 600; cursor: pointer; font-size: 13px; }

        .feedback-box { display: none; margin-top: 8px; padding: 8px; background: #334155; border-radius: 12px; text-align: left; }
        .feedback-btns { display: flex; gap: 8px; margin-top: 6px; }
        .feedback-btns button { flex: 1; padding: 8px; border-radius: 8px; border: none; font-weight: 600; cursor: pointer; font-size: 13px; }
        .btn-yes { background: #16a34a; color: white; }
        .btn-no { background: #dc2626; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <button class="circle-btn" onclick="resetApp()">✕</button>
            <span>the brick scanner</span>
            <button class="circle-btn">?</button>
        </div>

        <!-- Camera Dashboard Screen -->
        <div id="cameraScreen" class="camera-screen">
            <!-- Set Number Input -->
            <div class="set-input-box">
                <label for="setInput">LEGO Set Number (Optimizes Catalog Search)</label>
                <input type="text" id="setInput" class="set-input" placeholder="e.g. 75313, 42115">
            </div>

            <!-- Quality Warning Banner -->
            <div id="qualityWarning">⚠️ Lighting or clarity check: Make sure your pile photo is well-lit and in focus.</div>

            <div class="upload-row">
                <!-- Instruction Part Box -->
                <div class="upload-card" onclick="document.getElementById('instrFile').click()">
                    <span>🎯 Instruction Part</span>
                    <p id="instrName">Tap to capture</p>
                    <img id="instrPreview" class="preview-thumb">
                </div>
                <!-- Bricks Pile Box -->
                <div class="upload-card" onclick="document.getElementById('pileFile').click()">
                    <span>📸 Bricks Pile</span>
                    <p id="pileName">Tap to capture</p>
                    <img id="pilePreview" class="preview-thumb">
                </div>
            </div>

            <input type="file" id="instrFile" accept="image/*" capture="environment" style="display:none" onchange="handleFileSelect('instr')">
            <input type="file" id="pileFile" accept="image/*" capture="environment" style="display:none" onchange="handleFileSelect('pile')">

            <button class="scan-main-btn" id="scanBtn" disabled onclick="startScan()">🔍 AGENTIC SCAN</button>
        </div>

        <!-- Results & Scanner View -->
        <div id="result-container">
            <div id="description">Running multi-step agentic analysis & querying cache...</div>
            <div class="image-wrapper" id="imageWrapper">
                <img id="result-img" alt="Scanned result">
                <div id="correction-box">
                    <div class="handle handle-tl" data-handle="tl"></div>
                    <div class="handle handle-tr" data-handle="tr"></div>
                    <div class="handle handle-bl" data-handle="bl"></div>
                    <div class="handle handle-br" data-handle="br"></div>
                </div>
            </div>
            
            <!-- Save to Inventory / Storage Box -->
            <div class="storage-box-section" id="inventorySection">
                <input type="text" id="boxNameInput" class="storage-input" placeholder="Storage box name (e.g. Box #3)">
                <button class="storage-btn" onclick="saveToInventory()">Save Location 📦</button>
            </div>

            <div id="feedbackSection" class="feedback-box">
                <div id="feedback-text">Is this the correct part and color?</div>
                <div class="feedback-btns" id="feedback-btns-container">
                    <button class="btn-yes" onclick="sendFeedback('yes')">Yes 👍</button>
                    <button class="btn-no" onclick="enableResizeBox()">Inaccurate ❌</button>
                </div>
                <button id="submitCorrectionBtn" class="scan-main-btn" style="margin-top: 6px; display: none; font-size: 14px; padding: 10px;" onclick="submitCorrection()">Confirm Adjusted Box 🚀</button>
            </div>
        </div>
    </div>

    <script>
        let instrFileObj = null;
        let pileFileObj = null;
        let actionState = null;
        let startX, startY, boxX = 50, boxY = 50, boxW = 100, boxH = 100;
        let lastDetectedPart = "";

        function handleFileSelect(type) {
            const fileInput = document.getElementById(type + 'File');
            const file = fileInput.files[0];
            if (!file) return;

            if (type === 'instr') instrFileObj = file;
            if (type === 'pile') {
                pileFileObj = file;
                checkImageQuality(file);
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                document.getElementById(type + 'Name').innerText = "Selected ✓";
                const preview = document.getElementById(type + 'Preview');
                preview.src = e.target.result;
                preview.style.display = 'block';

                if (instrFileObj && pileFileObj) {
                    document.getElementById('scanBtn').removeAttribute('disabled');
                }
            };
            reader.readAsDataURL(file);
        }

        // UX Helper: Simple brightness/sharpness check heuristic
        function checkImageQuality(file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                const img = new Image();
                img.onload = () => {
                    const canvas = document.createElement('canvas');
                    canvas.width = 100;
                    canvas.height = 100;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, 100, 100);
                    const imgData = ctx.getImageData(0, 0, 100, 100);
                    let brightness = 0;
                    for (let i = 0; i < imgData.data.length; i += 4) {
                        brightness += (imgData.data[i] + imgData.data[i+1] + imgData.data[i+2]) / 3;
                    }
                    brightness = brightness / (100 * 100);
                    
                    const warning = document.getElementById('qualityWarning');
                    if (brightness < 40) {
                        warning.innerText = "⚠️ Low lighting detected. Ensure good light for accurate color matching!";
                        warning.style.display = "block";
                    } else if (brightness > 240) {
                        warning.innerText = "⚠️ Overexposed image detected. Watch out for glare on glossy bricks!";
                        warning.style.display = "block";
                    } else {
                        warning.style.display = "none";
                    }
                };
                img.src = e.target.result;
            };
            reader.readAsDataURL(file);
        }

        function resetApp() {
            document.getElementById('cameraScreen').classList.remove('hidden');
            document.getElementById('result-container').classList.remove('active');
            document.getElementById('correction-box').style.display = 'none';
            document.getElementById('submitCorrectionBtn').style.display = 'none';
            document.getElementById('feedbackSection').style.display = 'none';
            document.getElementById('qualityWarning').style.display = 'none';
            
            instrFileObj = null;
            pileFileObj = null;
            document.getElementById('setInput').value = '';
            document.getElementById('instrFile').value = '';
            document.getElementById('pileFile').value = '';
            document.getElementById('instrPreview').style.display = 'none';
            document.getElementById('pilePreview').style.display = 'none';
            document.getElementById('instrName').innerText = 'Tap to capture';
            document.getElementById('pileName').innerText = 'Tap to capture';
            document.getElementById('scanBtn').setAttribute('disabled', 'true');
        }

        function resizeImage(file, maxWidth = 2500) {
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const img = new Image();
                    img.onload = () => {
                        const canvas = document.createElement('canvas');
                        let width = img.width;
                        let height = img.height;
                        if (width > maxWidth) {
                            height = Math.round((height * maxWidth) / width);
                            width = maxWidth;
                        }
                        canvas.width = width;
                        canvas.height = height;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(img, 0, 0, width, height);
                        canvas.toBlob((blob) => {
                            resolve(new File([blob], file.name, { type: 'image/jpeg' }));
                        }, 'image/jpeg', 0.92);
                    };
                    img.src = e.target.result;
                };
                reader.readAsDataURL(file);
            });
        }

        async function startScan() {
            document.getElementById('cameraScreen').classList.add('hidden');
            const resContainer = document.getElementById('result-container');
            resContainer.classList.add('active');
            
            const descDiv = document.getElementById("description");
            const imgElement = document.getElementById("result-img");
            const feedbackSection = document.getElementById("feedbackSection");
            const setNumber = document.getElementById("setInput").value.trim();
            
            descDiv.innerText = "Step 1: Analyzing instruction sub-part & building assistant context...\nStep 2: Performing agentic sub-region pile scan...";
            imgElement.style.display = "none";
            feedbackSection.style.display = "none";

            try {
                const resizedInstr = await resizeImage(instrFileObj);
                const resizedPile = await resizeImage(pileFileObj);

                const formData = new FormData();
                formData.append("instruction_file", resizedInstr);
                formData.append("pile_file", resizedPile);
                formData.append("set_number", setNumber);
                
                const response = await fetch("/find-part", {
                    method: "POST",
                    body: formData
                });
                
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || "Server error");
                }
                
                descDiv.innerText = data.description;
                lastDetectedPart = data.description.split('\n')[0];
                imgElement.src = "data:image/jpeg;base64," + data.image;
                imgElement.style.display = "block";
                feedbackSection.style.display = "block";
            } catch (err) {
                descDiv.innerText = "Error: " + err.message;
            }
        }

        async function saveToInventory() {
            const boxName = document.getElementById("boxNameInput").value.trim();
            const setNumber = document.getElementById("setInput").value.trim();
            if (!boxName) {
                alert("Please enter a box name first!");
                return;
            }

            const response = await fetch("/save-inventory", {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ set_number: setNumber, part_name: lastDetectedPart, box_location: boxName })
            });
            const data = await response.json();
            if (data.status === "success") {
                document.getElementById("inventorySection").innerHTML = "<strong style='color: #34d399;'>Saved to inventory successfully! 🗄️</strong>";
            }
        }

        function sendFeedback(answer) {
            if (answer === 'yes') {
                document.getElementById("feedbackSection").innerHTML = "<strong>Awesome! Happy building! 🧱</strong>";
            }
        }

        function enableResizeBox() {
            document.getElementById("feedback-text").innerHTML = "<strong>Drag box to move, or use corners to resize! 🎯</strong>";
            document.getElementById("feedback-btns-container").style.display = "none";
            document.getElementById("submitCorrectionBtn").style.display = "block";

            const correctionBox = document.getElementById("correction-box");
            const imgElement = document.getElementById("result-img");

            boxW = imgElement.clientWidth * 0.25;
            boxH = imgElement.clientHeight * 0.25;
            boxX = (imgElement.clientWidth - boxW) / 2;
            boxY = (imgElement.clientHeight - boxH) / 2;

            updateBoxStyle();
            correctionBox.style.display = "block";

            correctionBox.onmousedown = (e) => {
                if (e.target.classList.contains('handle')) {
                    actionState = 'resize-' + e.target.dataset.handle;
                } else {
                    actionState = 'drag';
                }
                startX = e.clientX;
                startY = e.clientY;
                e.preventDefault();
            };

            window.onmouseup = () => { actionState = null; };
            window.onmousemove = handlePointerMove;

            correctionBox.ontouchstart = (e) => {
                if (e.target.classList.contains('handle')) {
                    actionState = 'resize-' + e.target.dataset.handle;
                } else {
                    actionState = 'drag';
                }
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                e.preventDefault();
            };

            window.ontouchend = () => { actionState = null; };
            window.ontouchmove = handleTouchMove;
        }

        function updateBoxStyle() {
            const box = document.getElementById("correction-box");
            box.style.left = boxX + 'px';
            box.style.top = boxY + 'px';
            box.style.width = boxW + 'px';
            box.style.height = boxH + 'px';
        }

        function handlePointerMove(e) {
            if (!actionState) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            startX = e.clientX;
            startY = e.clientY;
            processMovement(dx, dy);
        }

        function handleTouchMove(e) {
            if (!actionState) return;
            const dx = e.touches[0].clientX - startX;
            const dy = e.touches[0].clientY - startY;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            processMovement(dx, dy);
        }

        function processMovement(dx, dy) {
            if (actionState === 'drag') {
                boxX += dx;
                boxY += dy;
            } else if (actionState === 'resize-br') {
                boxW = Math.max(20, boxW + dx);
                boxH = Math.max(20, boxH + dy);
            } else if (actionState === 'resize-tl') {
                let newW = boxW - dx;
                let newH = boxH - dy;
                if (newW > 20) { boxX += dx; boxW = newW; }
                if (newH > 20) { boxY += dy; boxH = newH; }
            } else if (actionState === 'resize-tr') {
                let newW = boxW + dx;
                let newH = boxH - dy;
                if (newW > 20) { boxW = newW; }
                if (newH > 20) { boxY += dy; boxH = newH; }
            } else if (actionState === 'resize-bl') {
                let newW = boxW - dx;
                let newH = boxH + dy;
                if (newW > 20) { boxX += dx; boxW = newW; }
                if (newH > 20) { boxH = newH; }
            }
            updateBoxStyle();
        }

        async function submitCorrection() {
            const imgElement = document.getElementById("result-img");
            const displayedWidth = imgElement.clientWidth;
            const displayedHeight = imgElement.clientHeight;

            const xmin = Math.round((boxX / displayedWidth) * 1000);
            const ymin = Math.round((boxY / displayedHeight) * 1000);
            const xmax = Math.round(((boxX + boxW) / displayedWidth) * 1000);
            const ymax = Math.round(((boxY + boxH) / displayedHeight) * 1000);

            document.getElementById("correction-box").style.display = "none";
            document.getElementById("feedbackSection").innerHTML = "<strong>Thank you! Custom correction box saved. 🚀</strong>";
        }
    </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def read_root():
    return html

@app.post("/find-part")
async def find_part(
    instruction_file: UploadFile = File(...), 
    pile_file: UploadFile = File(...),
    set_number: str = Form(default="")
):
    try:
        instr_bytes = await instruction_file.read()
        pile_bytes = await pile_file.read()

        # Feature 4: Performance Caching (Hash-based cache key lookup)
        hasher = hashlib.sha256()
        hasher.update(instr_bytes)
        hasher.update(pile_bytes)
        hasher.update(set_number.encode('utf-8'))
        cache_key = hasher.hexdigest()

        conn = sqlite3.connect('brick_scanner.db')
        cursor = conn.cursor()
        cursor.execute("SELECT description, image_b64 FROM scan_cache WHERE hash_key = ?", (cache_key,))
        cached_result = cursor.fetchone()
        conn.close()

        if cached_result:
            return {
                "status": "success",
                "description": cached_result[0] + "\n(⚡ Retrieved from cached agent scan)",
                "image": cached_result[1]
            }

        instr_image = Image.open(io.BytesIO(instr_bytes))
        pile_image = Image.open(io.BytesIO(pile_bytes))

        set_context = f" The target LEGO set number is {set_number}." if set_number.strip() else ""

        # Feature 1 & 3: Multi-step agentic workflow + Smart building assistant context
        prompt_text = (
            f"You are an advanced LEGO agentic builder and part identifier using LDraw and BrickLink catalog standards.{set_context} "
            "Perform a 2-step analysis: "
            "Step 1: Isolate and inspect the target part from the instruction image (1), identifying its exact LDraw ID, exact color name, and standard building assembly context (e.g. step role in the manual). "
            "Step 2: Sub-region scan of the pile image (2) to locate the exact matching part matching geometry and color strictly. "
            "CRITICAL REQUIREMENT: You MUST write your entire response strictly in ENGLISH. "
            "Provide a short description including the part's estimated LDraw/BrickLink ID, color name, and building context. "
            "On the very last line, output ONLY 4 numbers separated by commas for the bounding box [ymin, xmin, ymax, xmax] scaled from 0 to 1000."
        )

        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=[instr_image, pile_image, prompt_text]
        )

        text_response = response.text.strip()
        lines = text_response.split('\n')
        
        box = None
        description = text_response
        
        for line in reversed(lines):
            numbers = re.findall(r'\d+', line)
            if len(numbers) == 4:
                box = [int(n) for n in numbers]
                description = text_response.replace(line, "").strip()
                break

        draw_img = pile_image.copy()
        width, height = draw_img.size

        if box and len(box) == 4:
            ymin, xmin, ymax, xmax = box
            
            box_height = ymax - ymin
            box_width = xmax - xmin
            padding_y = int(box_height * 0.2)
            padding_x = int(box_width * 0.2)
            
            ymin = max(0, ymin - padding_y)
            xmin = max(0, xmin - padding_x)
            ymax = min(1000, ymax + padding_y)
            xmax = min(1000, xmax + padding_x)

            left = (xmin / 1000.0) * width
            top = (ymin / 1000.0) * height
            right = (xmax / 1000.0) * width
            bottom = (ymax / 1000.0) * height

            draw = ImageDraw.Draw(draw_img)
            line_width = max(4, int(width / 200))
            draw.rectangle([left, top, right, bottom], outline="red", width=line_width)

        buffered = io.BytesIO()
        draw_img.save(buffered, format="JPEG", quality=95)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # Save to cache database
        conn = sqlite3.connect('brick_scanner.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO scan_cache (hash_key, description, image_b64) VALUES (?, ?, ?)", 
                       (cache_key, description, img_str))
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "description": description,
            "image": img_str
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save-inventory")
async def save_inventory(data: dict):
    try:
        set_number = data.get("set_number", "")
        part_name = data.get("part_name", "")
        box_location = data.get("box_location", "")

        conn = sqlite3.connect('brick_scanner.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO inventory (set_number, part_name, box_location) VALUES (?, ?, ?)",
                       (set_number, part_name, box_location))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)