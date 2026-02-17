import { NextResponse } from 'next/server'
import { verifyIdToken } from '@/lib/firebase-admin'
import * as XLSX from 'xlsx'

// Python microservice URL - set in environment variables
// For local development: NEXT_PUBLIC_PYTHON_SERVICE_URL=http://localhost:5000
// For production: NEXT_PUBLIC_PYTHON_SERVICE_URL=https://groundwater-mapper.onrender.com
const PYTHON_SERVICE_URL = process.env.NEXT_PUBLIC_PYTHON_SERVICE_URL

export const dynamic = 'force-dynamic'

// Keywords to exclude from parameter selection (matching Streamlit app)
const EXCLUDE_KEYWORDS = [
    'sample date',
    'time',
    'date',
    'easting',
    'northing',
    'lati',
    'longi',
    'comments',
    'well id',
    'mga2020',
    'unknown',
    'unit',
    'lor',
    'guideline',
    'trigger'
]

// Column name variations for coordinates
const LAT_COLUMNS = ['latitude', 'lat', 'y']
const LON_COLUMNS = ['longitude', 'lon', 'long', 'lng', 'x', 'easting']
const WELL_ID_COLUMNS = ['well id', 'wellid', 'well', 'site', 'site id', 'location']

// Helper function to verify Firebase ID token from Authorization header
async function getAuthenticatedUserId(request: Request): Promise<string | null> {
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        console.log('[Auth] No Bearer token in Authorization header')
        return null
    }

    const idToken = authHeader.substring(7) // Remove 'Bearer ' prefix
    console.log('[Auth] Verifying ID token...')

    const decodedToken = await verifyIdToken(idToken)
    if (!decodedToken) {
        console.log('[Auth] Token verification failed')
        return null
    }

    console.log('[Auth] Token verified for user:', decodedToken.uid)
    return decodedToken.uid
}

// Vercel has a hard limit of 4.5MB for serverless function request bodies
// This endpoint now primarily returns the Python service URL for direct uploads
// and only processes small files locally as fallback

export async function GET(): Promise<NextResponse> {
    // Return the Python service URL so frontend can upload directly
    return NextResponse.json({
        pythonServiceUrl: PYTHON_SERVICE_URL || null,
        message: PYTHON_SERVICE_URL
            ? 'Use the Python service URL for direct file upload to avoid Vercel size limits'
            : 'Python service not configured'
    })
}

export async function POST(request: Request): Promise<NextResponse> {
    console.log('[Preview API] Request received')
    console.log('[Preview API] Python Service URL:', PYTHON_SERVICE_URL || 'NOT CONFIGURED')

    try {
        // Verify Firebase ID token from Authorization header
        const userId = await getAuthenticatedUserId(request)

        if (!userId) {
            console.log('[Preview API] Unauthorized - no valid token')
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        // Check content length before processing
        const contentLength = request.headers.get('content-length')
        const fileSize = contentLength ? parseInt(contentLength, 10) : 0
        console.log('[Preview API] Request content length:', fileSize, 'bytes (~', Math.round(fileSize / 1024 / 1024 * 100) / 100, 'MB)')

        // Vercel limit is 4.5MB - if file is larger, we need to use Python service directly
        const VERCEL_LIMIT = 4.5 * 1024 * 1024 // 4.5MB in bytes

        if (fileSize > VERCEL_LIMIT) {
            console.log('[Preview API] File exceeds Vercel limit, Python service required')
            if (!PYTHON_SERVICE_URL) {
                return NextResponse.json({
                    error: 'File too large for Vercel (limit 4.5MB). Python service not configured.',
                    fileSize: fileSize,
                    limit: VERCEL_LIMIT,
                    pythonServiceUrl: null
                }, { status: 413 })
            }
            // Return info so frontend can upload directly to Python service
            return NextResponse.json({
                error: 'File too large. Please use direct upload to Python service.',
                pythonServiceUrl: PYTHON_SERVICE_URL,
                fileSize: fileSize,
                limit: VERCEL_LIMIT,
                requiresDirectUpload: true
            }, { status: 413 })
        }

        const formData = await request.formData()
        const file = formData.get('file') as File

        if (!file) {
            console.log('[Preview API] No file provided')
            return NextResponse.json({ error: 'No file provided' }, { status: 400 })
        }

        console.log('[Preview API] File received:', file.name, 'size:', file.size, 'bytes')

        // If Python service URL is configured, use it
        if (PYTHON_SERVICE_URL) {
            try {
                console.log('[Preview API] Forwarding to Python service:', PYTHON_SERVICE_URL)

                // Convert file to buffer for Python service
                const buffer = Buffer.from(await file.arrayBuffer())

                // Forward to Python service
                const pythonFormData = new FormData()
                pythonFormData.append('file', new Blob([buffer]), file.name)
                pythonFormData.append('use_llamaparse', 'true')

                const pythonResponse = await fetch(`${PYTHON_SERVICE_URL}/preview`, {
                    method: 'POST',
                    body: pythonFormData,
                })

                console.log('[Preview API] Python service response status:', pythonResponse.status)

                if (pythonResponse.ok) {
                    const pythonData = await pythonResponse.json()
                    console.log('[Preview API] Python service success, columns:', pythonData.columns?.length || 0)
                    return NextResponse.json({
                        success: true,
                        sheets: pythonData.sheets || [],
                        columns: pythonData.columns,
                        availableParameters: pythonData.numeric_columns,
                        rowCount: pythonData.row_count,
                        sampleData: pythonData.preview,
                        source: 'python',
                        parse_method: pythonData.parse_method
                    })
                } else {
                    // Handle Python service error - try to get error message
                    const errorText = await pythonResponse.text()
                    console.error('[Preview API] Python service error:', errorText)
                    // Return error as JSON so frontend can handle it
                    return NextResponse.json({
                        error: 'Python service error: ' + errorText.substring(0, 100)
                    }, { status: 502 })
                }
            } catch (pythonError) {
                console.error('[Preview API] Error calling Python service:', pythonError)
                // Fall through to Node.js implementation
            }
        } else {
            console.log('[Preview API] Python service URL not configured, using Node.js fallback')
        }

        // Node.js implementation (fallback)
        // Read Excel file
        const buffer = Buffer.from(await file.arrayBuffer())
        const workbook = XLSX.read(buffer, { type: 'buffer' })
        const sheetNames = workbook.SheetNames

        // Get all columns and sample data from first sheet for initial preview
        const firstSheetName = sheetNames[0]
        const worksheet = workbook.Sheets[firstSheetName]
        const data = XLSX.utils.sheet_to_json(worksheet)

        if (!data || data.length === 0) {
            return NextResponse.json({ error: 'No data found in Excel file' }, { status: 400 })
        }

        // Get all columns from first row
        const firstRow = data[0] as Record<string, any>
        const allColumns = Object.keys(firstRow)

        // Find coordinate columns
        const latColumns = allColumns.filter(col =>
            LAT_COLUMNS.some(lat => col.toLowerCase().includes(lat))
        )
        const lonColumns = allColumns.filter(col =>
            LON_COLUMNS.some(lon => col.toLowerCase().includes(lon))
        )
        const wellIdColumns = allColumns.filter(col =>
            WELL_ID_COLUMNS.some(well => col.toLowerCase().includes(well))
        )

        // Filter available parameters (exclude non-numeric and irrelevant columns)
        // This matches the Streamlit app's logic
        const availableParameters = allColumns.filter(col => {
            const colLower = col.toLowerCase()

            // Check if column name contains excluded keywords
            if (EXCLUDE_KEYWORDS.some(keyword => colLower.includes(keyword))) {
                return false
            }

            // Check if it's a coordinate column
            if (LAT_COLUMNS.some(lat => colLower === lat || colLower.includes('latitude')) ||
                LON_COLUMNS.some(lon => colLower === lon || colLower.includes('longitude'))) {
                return false
            }

            // Check if it contains numeric data (at least some valid numbers)
            const values = data.slice(0, 20).map((row: any) => row[col])
            const validNumbers = values.filter((v: any) => {
                if (v === null || v === undefined || v === '') return false
                const num = parseFloat(v)
                return !isNaN(num) && isFinite(num)
            })

            // Only include if at least 30% of values are valid numbers
            return validNumbers.length / values.length > 0.3
        })

        // Get sample data (first 5 rows)
        const sampleData = data.slice(0, 5).map((row: any) => row)

        return NextResponse.json({
            success: true,
            sheetNames,
            columns: allColumns,
            availableParameters,  // Filtered columns for parameter dropdown
            latColumns,
            lonColumns,
            wellIdColumns,
            rowCount: data.length,
            sampleData
        })
    } catch (error: any) {
        console.error('Error previewing file:', error)
        return NextResponse.json({ error: error.message || 'Failed to preview file' }, { status: 500 })
    }
}
