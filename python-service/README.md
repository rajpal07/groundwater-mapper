# Groundwater Mapper Python Microservice

A Flask-based backend that provides Excel processing and map generation capabilities for the Groundwater Mapper Next.js application.

## Features

- **Excel File Parsing**: Process multi-sheet Excel workbooks
- **AI-Powered Parsing**: Optional LlamaCloud integration for intelligent Excel parsing
- **Contour Generation**: Generate contour maps using scipy interpolation
- **UTM Zone Detection**: Auto-detect Australian UTM zones from coordinates
- **Google Earth Engine**: Optional integration for satellite imagery

## Quick Start

### 1. Install Dependencies

```bash
cd python-service
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

Edit `.env`:
```env
# LlamaCloud API Key (optional)
LLAMA_CLOUD_API_KEY=your_api_key_here

# Google Earth Engine (optional)
GOOGLE_EE_SERVICE_ACCOUNT={"type":"service_account",...}
```

### 3. Run the Service

```bash
# Development
python app.py

# The service runs on http://localhost:5000
```

### 4. Test the Service

```bash
# Health check
curl http://localhost:5000/health

# Preview endpoint (using curl)
curl -X POST http://localhost:5000/preview \
  -F "file=@your_file.xlsx"
```

## API Endpoints

### GET /health
Check if service is running.

**Response:**
```json
{
  "status": "ok",
  "llamaparse": true,
  "gee": false
}
```

### POST /preview
Analyze Excel file and return available parameters.

**Request:**
- `file`: Excel file (multipart/form-data)
- `useAI`: (optional) Use AI parsing - "true" or "false"
- `apiKey`: (optional) LlamaCloud API key

**Response:**
```json
{
  "success": true,
  "sheetNames": ["Sheet1", "Sheet2"],
  "columns": ["Well ID", "Easting", "Northing", "pH", "EC"],
  "availableParameters": ["pH", "EC"],
  "latColumns": ["Latitude"],
  "lonColumns": ["Longitude"],
  "rowCount": 100
}
```

### POST /process
Generate contour map from Excel data.

**Request:**
- `file`: Excel file (multipart/form-data)
- `parameter`: Column name to visualize
- `colormap`: Color scheme (viridis, plasma, RdYlBu_r, etc.)
- `sheetName`: Sheet name or index
- `useAI`: (optional) Use AI parsing
- `apiKey`: (optional) LlamaCloud API key

**Response:**
```json
{
  "success": true,
  "imageBase64": "iVBORw0KGgo...",
  "bounds": [[-34.5, 115.0], [-33.0, 117.0]],
  "points": [
    {"lat": -34.1, "lon": 115.5, "id": 0, "name": "WELL-001", "value": 7.2}
  ],
  "parameter": "pH",
  "colormap": "viridis"
}
```

## Integration with Next.js

### Option 1: Use as External API (Recommended for Production)

Update your Next.js app to call the Python service directly:

```typescript
// app/api/process/route.ts
const PYTHON_SERVICE_URL = process.env.PYTHON_SERVICE_URL || 'http://localhost:5000'

export async function POST(request: Request) {
  const formData = await request.formData()
  
  // Forward to Python service
  const response = await fetch(`${PYTHON_SERVICE_URL}/process`, {
    method: 'POST',
    body: formData
  })
  
  const data = await response.json()
  return NextResponse.json(data)
}
```

### Option 2: Run Alongside Next.js

Start both services in separate terminals:

```bash
# Terminal 1: Python service
cd python-service && python app.py

# Terminal 2: Next.js
cd .. && npm run dev
```

## Available Colormaps

- viridis
- plasma
- inferno
- magma
- cividis
- RdYlBu_r
- RdYlBu
- Spectral_r
- coolwarm
- blues
- greens
- reds
- YlOrRd
- YlGn
- YlGnBu

## Docker Deployment

```bash
# Build
docker build -t groundwater-mapper-service .

# Run
docker run -p 5000:5000 -e LLAMA_CLOUD_API_KEY=your_key groundwater-mapper-service
```

## Deploy to Render.com (Recommended)

### Option 1: Deploy via GitHub (Recommended)

1. Push your code to GitHub:
   ```bash
   cd groundwater-mapper_pushed
   git add python-service/
   git commit -m "Add Python microservice"
   git push origin main
   ```

2. Go to [Render.com](https://render.com) and sign in

3. Create a new Web Service:
   - Connect your GitHub repository
   - Select the `python-service` folder
   - Configure:
     - Name: `groundwater-mapper-api`
     - Region: `Oregon`
     - Branch: `main`
     - Build Command: `pip install -r requirements.txt`
     - Start Command: `python app.py`

4. Add Environment Variables in Render dashboard:
   - `PYTHON_VERSION`: `3.11`
   - `LLAMA_CLOUD_API_KEY`: Your API key from earlier
   - `GOOGLE_EE_SERVICE_ACCOUNT`: Your service account JSON

5. Click "Deploy"

6. After deployment, you'll get a URL like: `https://groundwater-mapper-api.onrender.com`

### Option 2: Deploy using render.yaml

1. Push `render.yaml` to your GitHub repo

2. Render will auto-detect and deploy

### Update Next.js to use Render URL

Once deployed, update your Next.js `.env.local`:
```env
NEXT_PUBLIC_PYTHON_API=https://groundwater-mapper-api.onrender.com
```

Then update the API route to use this URL.

## Project Structure

```
python-service/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── Dockerfile         # Docker configuration
├── .env.example       # Environment variables template
└── README.md          # This file
```
