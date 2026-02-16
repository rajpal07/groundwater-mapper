# Groundwater Mapper - Next.js Application Specification

## Project Overview
- **Project Name**: Groundwater Mapper Pro
- **Type**: Full-stack web application (Next.js + Node.js)
- **Core Functionality**: Convert Excel groundwater data into interactive contour maps with aquifer analysis, arrow verification, and smart Excel export capabilities
- **Target Users**: Environmental consultants, hydrogeologists, groundwater analysts

---

## Architecture

### Tech Stack
- **Frontend**: Next.js 14 (App Router), React, TypeScript
- **Backend**: Node.js + Express.js (API routes in Next.js or separate Express)
- **Database**: PostgreSQL with Prisma ORM
- **Authentication**: NextAuth.js with Google Provider
- **Maps**: Leaflet.js / Folium (Python) converted to JavaScript
- **Data Processing**: Python scripts wrapped via Node.js child processes

### Project Structure
```
/groundwater-mapper-web
├── /app                    # Next.js App Router
│   ├── /api                # API Routes
│   │   ├── /auth           # Authentication endpoints
│   │   ├── /projects       # Project CRUD
│   │   ├── /maps           # Map generation
│   │   └── /upload         # File upload
│   ├── /(auth)             # Auth pages (login, register)
│   ├── /(dashboard)        # Protected dashboard pages
│   └── /page.tsx           # Landing page
├── /components             # React components
│   ├── /ui                 # Reusable UI components
│   ├── /maps               # Map components
│   └── /forms              # Form components
├── /lib                    # Utilities
│   ├── /db                 # Database utilities
│   ├── /auth               # Auth configuration
│   └── /python             # Python script runners
├── /public                 # Static assets
└── /scripts                # Python processing scripts (converted)
```

---

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email        VARCHAR(255) UNIQUE NOT NULL,
    name         VARCHAR(255),
    image        VARCHAR(500),
    createdAt    TIMESTAMP DEFAULT NOW(),
    updatedAt    TIMESTAMP DEFAULT NOW()
);
```

### Projects Table
```sql
CREATE TABLE projects (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    userId        UUID REFERENCES users(id) ON DELETE CASCADE,
    name          VARCHAR(255) NOT NULL,
    description   TEXT,
    status        VARCHAR(50) DEFAULT 'active',
    createdAt     TIMESTAMP DEFAULT NOW(),
    updatedAt     TIMESTAMP DEFAULT NOW()
);
```

### Maps Table
```sql
CREATE TABLE maps (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    projectId     UUID REFERENCES projects(id) ON DELETE CASCADE,
    name          VARCHAR(255) NOT NULL,
    parameter     VARCHAR(100),
    colormap      VARCHAR(50),
    excelData     JSONB,
    processedData JSONB,
    mapHtml       TEXT,
    createdAt     TIMESTAMP DEFAULT NOW()
);
```

---

## UI/UX Specification

### Design System

#### Color Palette
- **Primary**: `#006645` (Deep Green)
- **Primary Dark**: `#00493D` (Forest Green)
- **Secondary**: `#E3F3F1` (Light Mint)
- **Accent**: `#636466` (Gray)
- **Background**: `#FFFFFF`
- **Surface**: `#F8F9FA`
- **Error**: `#DC3545`
- **Success**: `#28A745`

#### Typography
- **Primary Font**: Montserrat (Google Fonts)
- **Secondary Font**: Libre Baskerville (Headings)
- **Body Size**: 18px
- **Heading Sizes**: H1: 35px, H2: 28px, H3: 24px

#### Spacing System
- Base unit: 8px
- Sections: 80px vertical padding
- Components: 16px-24px padding

### Pages

#### 1. Landing Page
- Hero section with video/animated background
- Features overview (3 cards)
- CTA buttons (Get Started, View Demo)
- Footer with links

#### 2. Authentication Pages
- Clean centered card layout
- Google Sign-In button
- Terms & Privacy links

#### 3. Dashboard
- Sidebar navigation
- Project cards grid
- Quick stats
- Recent maps list

#### 4. Map Editor
- Split layout: Controls | Map Preview
- File upload zone
- Parameter selector
- Color scheme picker
- Generate & Download buttons

---

## Functionality Specification

### Core Features

#### 1. Authentication
- Google OAuth 2.0 via NextAuth.js
- Session management
- Protected routes
- User profile sync

#### 2. Project Management
- Create new project
- Edit project details
- Delete project
- List user's projects
- Share project (future)

#### 3. Map Generation
- Excel file upload (.xlsx)
- Multi-sheet detection
- AI-powered data extraction (LlamaParse API integration)
- Coordinate system detection (Lat/Lon, UTM)
- Australian UTM zone auto-detection
- Aquifer stratification analysis
- Interpolation (linear, cubic, hybrid)
- Contour generation
- Arrow flow direction calculation
- Interactive map rendering
- HTML export

#### 4. Arrow Verification
- EPA method verification
- AI data processing
- Flow direction validation

#### 5. Smart Excel Export
- Threshold detection
- Conditional formatting
- Excel analysis

### API Endpoints

#### Authentication
- `GET /api/auth/[...nextauth]` - NextAuth handlers

#### Projects
- `GET /api/projects` - List user projects
- `POST /api/projects` - Create project
- `GET /api/projects/[id]` - Get project details
- `PUT /api/projects/[id]` - Update project
- `DELETE /api/projects/[id]` - Delete project

#### Maps
- `GET /api/maps?projectId=` - List maps in project
- `POST /api/maps` - Generate new map
- `GET /api/maps/[id]` - Get map details
- `DELETE /api/maps/[id]` - Delete map

#### Processing
- `POST /api/process/excel` - Process Excel file
- `POST /api/process/verify` - Verify arrows

---

## Python to JavaScript Conversion

### Required Python Scripts (to be converted/wrapped)

1. **src/data.py** → JavaScript data processing module
2. **src/geo.py** → JavaScript geo utilities
3. **src/aquifer.py** → JavaScript aquifer analysis
4. **src/visualization.py** → JavaScript map rendering (using Leaflet)
5. **src/templates.py** → JavaScript HTML injection
6. **src/sheet_agent.py** → Node.js integration with LlamaParse API

### Python Dependencies (for wrapped scripts)
- pandas
- numpy
- scipy
- matplotlib
- openpyxl
- pyproj
- shapely
- llama-index
- llama-parse

---

## Acceptance Criteria

### Authentication
- [ ] User can sign in with Google
- [ ] User session persists across page refreshes
- [ ] Protected routes redirect to login

### Projects
- [ ] User can create a new project
- [ ] User can view all their projects
- [ ] User can edit project details
- [ ] User can delete project

### Maps
- [ ] User can upload Excel file
- [ ] App detects sheets automatically
- [ ] App generates interactive map
- [ ] Map displays contour overlay
- [ ] Map shows well points with tooltips
- [ ] User can download map as HTML
- [ ] Map is saved to database

### UI/UX
- [ ] Responsive design works on mobile
- [ ] Loading states shown during processing
- [ ] Error messages are user-friendly
- [ ] Navigation is intuitive

---

## Environment Variables

```env
# Database
DATABASE_URL="postgresql://..."

# NextAuth
NEXTAUTH_URL="http://localhost:3000"
NEXTAUTH_SECRET="your-secret"

# Google OAuth
GOOGLE_CLIENT_ID="your-client-id"
GOOGLE_CLIENT_SECRET="your-client-secret"

# LlamaParse API
LLAMA_CLOUD_API_KEY="your-llama-key"

# Google Earth Engine (optional)
EARTHENGINE_TOKEN="..."
```

---

## Deployment

### Production Checklist
- [ ] Set up PostgreSQL database
- [ ] Configure Google OAuth credentials
- [ ] Set environment variables
- [ ] Build production bundle
- [ ] Set up reverse proxy (Nginx)
- [ ] Configure SSL/HTTPS
