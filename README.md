# Groundwater Mapper Web Application

A modern web application for groundwater mapping, converted from Streamlit to Next.js + Node.js stack. This application allows users to create projects, upload Excel data, and generate interactive groundwater maps.

## Features

- **User Authentication**: Google OAuth sign-in for secure access
- **Project Management**: Create and manage multiple groundwater mapping projects
- **Data Upload**: Upload Excel files (.xlsx, .xls) with groundwater data
- **Map Generation**: Generate interpolated groundwater level maps
- **Aquifer Analysis**: Automatic aquifer stratification detection
- **Interactive Maps**: View and explore generated maps in an interactive viewer

## Tech Stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS
- **Backend**: Next.js API Routes, Node.js
- **Database**: PostgreSQL with Prisma ORM
- **Authentication**: NextAuth.js with Google OAuth
- **Maps**: Leaflet.js for interactive map visualization
- **Data Processing**: Python (pandas, scipy, folium) for advanced interpolation

## Prerequisites

1. **Node.js** (v18 or later)
2. **Python** (v3.9 or later)
3. **PostgreSQL** (v14 or later)
4. **Google Cloud Console** project with OAuth credentials

## Installation

### 1. Clone and Setup Next.js

```bash
cd groundwater-mapper-web

# Install Node.js dependencies
npm install

# Copy environment variables
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` with your credentials:

```env
# Database
DATABASE_URL="postgresql://user:password@localhost:5432/groundwater_mapper"

# NextAuth
NEXTAUTH_URL="http://localhost:3000"
NEXTAUTH_SECRET="your-secret-key"

# Google OAuth
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
```

### 3. Setup Database

```bash
# Create PostgreSQL database
createdb groundwater_mapper

# Run Prisma migrations
npx prisma migrate dev
```

### 4. Setup Python Environment

```bash
# Create virtual environment and install dependencies
cd scripts
python setup.py

# Or manually:
python -m venv ../venv
pip install -r requirements.txt
```

## Running the Application

### Development Mode

```bash
# Start the Next.js development server
npm run dev
```

Visit http://localhost:3000

### Production Mode

```bash
# Build the application
npm run build

# Start the production server
npm start
```

## Project Structure

```
groundwater-mapper-web/
├── app/                    # Next.js App Router pages
│   ├── api/               # API routes
│   │   ├── auth/          # NextAuth endpoints
│   │   ├── maps/          # Map CRUD operations
│   │   ├── preview/       # Excel file preview
│   │   ├── process/       # Map processing
│   │   └── projects/      # Project CRUD
│   ├── auth/              # Auth pages
│   └── dashboard/         # Protected dashboard
├── components/            # React components
├── lib/                  # Utility libraries
│   ├── auth.ts           # NextAuth config
│   └── db.ts             # Prisma client
├── prisma/               # Database schema
├── scripts/              # Python processing scripts
│   ├── process_map.py    # Main processing script
│   └── requirements.txt   # Python dependencies
└── public/               # Static assets
```

## Usage

### Creating a Project

1. Sign in with Google
2. Click "New Project" on the dashboard
3. Enter a project name and description
4. Click "Create"

### Creating a Map

1. Open a project
2. Click "New Map"
3. Upload an Excel file with columns:
   - Easting (X coordinate)
   - Northing (Y coordinate)
   - Parameter (e.g., GW Level, Depth to Water)
4. Select the parameter column to visualize
5. Choose a colormap
6. Click "Generate Map"

### Excel Data Format

Your Excel file should have the following structure:

| Easting | Northing | GW Level | ... |
|---------|----------|----------|-----|
| 500000  | 4500000  | 25.5     | ... |
| 500100  | 4500100  | 26.2     | ... |

## API Endpoints

### Authentication
- `GET /api/auth/[...nextauth]` - NextAuth handlers

### Projects
- `GET /api/projects` - List user projects
- `POST /api/projects` - Create project
- `DELETE /api/projects?id={id}` - Delete project

### Maps
- `GET /api/maps?projectId={id}` - List project maps
- `POST /api/maps` - Create new map
- `DELETE /api/maps?id={id}` - Delete map

### Processing
- `POST /api/process` - Process Excel and generate map
- `POST /api/preview` - Preview Excel file columns

## Environment Variables Reference

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `NEXTAUTH_URL` | Application URL |
| `NEXTAUTH_SECRET` | Secret for session encryption |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret |

## License

This project is for demonstration purposes. See the original Streamlit repository for the source functionality.
