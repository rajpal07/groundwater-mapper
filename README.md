# Groundwater Elevation Mapper

A Streamlit application for generating interactive groundwater contour maps from Excel data and KMZ files.

## Features

- Upload Excel files with groundwater elevation data
- Upload KMZ files for reference points
- Generate interactive contour maps with Folium
- Automatic UTM zone detection
- Visual overlay of contours on map

## Deployment on Vercel

### Prerequisites
- GitHub account
- Vercel account (sign up at [vercel.com](https://vercel.com))

### Steps

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Deploy on Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - Vercel will automatically detect the `vercel.json` configuration
   - Click "Deploy"

3. **Environment Variables** (if needed)
   - No environment variables required for basic deployment

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   streamlit run app.py
   ```

## Project Structure

```
.
├── app.py              # Main Streamlit application
├── utils.py            # Utility functions for data processing
├── requirements.txt    # Python dependencies
├── vercel.json         # Vercel deployment configuration
└── README.md           # This file
```

## Usage

1. Upload an Excel file (.xlsx) containing groundwater data
2. Optionally upload a KMZ file for reference points
3. Click "Generate Map"
4. The interactive map will open in a new browser tab

## Technologies Used

- **Streamlit** - Web application framework
- **Folium** - Interactive map visualization
- **GeoPandas** - Geospatial data processing
- **Pandas** - Data manipulation
- **NumPy & SciPy** - Numerical computing and interpolation
