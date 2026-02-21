import { NextResponse } from 'next/server'
import { verifyIdToken } from '@/lib/firebase-admin'
import { previewExcelFromBuffer, getPythonServiceUrl } from '@/lib/python-api'
import * as XLSX from 'xlsx'

export const dynamic = 'force-dynamic'

// Keywords to exclude from parameter selection (for Node.js fallback)
const EXCLUDE_KEYWORDS = [
    'sample date', 'time', 'date', 'easting', 'northing',
    'lati', 'longi', 'comments', 'well id', 'mga2020',
    'unknown', 'unit', 'lor', 'guideline', 'trigger'
]

// Column name variations for coordinates (for Node.js fallback)
const LAT_COLUMNS = ['latitude', 'lat', 'y']
const LON_COLUMNS = ['longitude', 'lon', 'long', 'lng', 'x', 'easting']

/**
 * Verify Firebase ID token from Authorization header
 */
async function getAuthenticatedUserId(request: Request): Promise<string | null> {
    const authHeader = request.headers.get('Authorization')
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return null
    }

    const idToken = authHeader.substring(7)
    const decodedToken = await verifyIdToken(idToken)
    return decodedToken?.uid || null
}

/**
 * GET /api/preview
 * Returns the Python service URL for direct uploads
 */
export async function GET(): Promise<NextResponse> {
    const pythonServiceUrl = getPythonServiceUrl()
    return NextResponse.json({
        pythonServiceUrl: pythonServiceUrl || null,
        message: pythonServiceUrl
            ? 'Use the Python service URL for direct file upload to avoid Vercel size limits'
            : 'Python service not configured'
    })
}

/**
 * POST /api/preview
 * Preview Excel file columns and data
 * Proxies to FastAPI backend, with Node.js fallback
 */
export async function POST(request: Request): Promise<NextResponse> {
    console.log('[Preview API] Request received')

    try {
        // Verify Firebase ID token
        const userId = await getAuthenticatedUserId(request)
        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        // Check content length against Vercel limit
        const contentLength = request.headers.get('content-length')
        const fileSize = contentLength ? parseInt(contentLength, 10) : 0
        const VERCEL_LIMIT = 4.5 * 1024 * 1024 // 4.5MB

        if (fileSize > VERCEL_LIMIT) {
            const pythonServiceUrl = getPythonServiceUrl()
            if (!pythonServiceUrl) {
                return NextResponse.json({
                    error: 'File too large for Vercel (limit 4.5MB). Python service not configured.',
                    fileSize,
                    limit: VERCEL_LIMIT,
                    pythonServiceUrl: null
                }, { status: 413 })
            }

            return NextResponse.json({
                error: 'File too large. Please use direct upload to Python service.',
                pythonServiceUrl,
                fileSize,
                limit: VERCEL_LIMIT,
                requiresDirectUpload: true
            }, { status: 413 })
        }

        // Parse form data
        const formData = await request.formData()
        const file = formData.get('file') as File

        if (!file) {
            return NextResponse.json({ error: 'No file provided' }, { status: 400 })
        }

        console.log('[Preview API] File received:', file.name, 'size:', file.size, 'bytes')

        // Get auth token for Python API
        const authHeader = request.headers.get('Authorization')
        const token = authHeader?.substring(7) || ''

        // Convert file to buffer
        const buffer = Buffer.from(await file.arrayBuffer())

        // Try Python API first
        const pythonServiceUrl = getPythonServiceUrl()
        if (pythonServiceUrl) {
            try {
                console.log('[Preview API] Forwarding to FastAPI backend:', pythonServiceUrl)

                const result = await previewExcelFromBuffer(buffer, file.name, token, true)

                console.log('[Preview API] FastAPI success, columns:', result.columns?.length || 0)

                return NextResponse.json({
                    success: true,
                    sheets: result.sheets || [],
                    columns: result.columns,
                    availableParameters: result.numeric_columns,
                    rowCount: result.row_count,
                    sampleData: result.preview,
                    coordinateSystem: result.coordinate_system,
                    source: 'fastapi',
                    parseMethod: result.parse_method
                })
            } catch (pythonError: any) {
                console.error('[Preview API] FastAPI error:', pythonError.message)
                // Fall through to Node.js fallback
            }
        }

        // Node.js fallback implementation
        console.log('[Preview API] Using Node.js fallback')
        return await previewWithNodeJS(buffer)

    } catch (error: any) {
        console.error('[Preview API] Error:', error)
        return NextResponse.json({
            error: error.message || 'Failed to preview file'
        }, { status: 500 })
    }
}

/**
 * Node.js fallback for Excel preview using xlsx library
 */
async function previewWithNodeJS(buffer: Buffer): Promise<NextResponse> {
    const workbook = XLSX.read(buffer, { type: 'buffer' })
    const sheetNames = workbook.SheetNames

    // Get data from first sheet
    const firstSheetName = sheetNames[0]
    const worksheet = workbook.Sheets[firstSheetName]
    const data = XLSX.utils.sheet_to_json(worksheet)

    if (!data || data.length === 0) {
        return NextResponse.json({ error: 'No data found in Excel file' }, { status: 400 })
    }

    // Get all columns
    const firstRow = data[0] as Record<string, any>
    const allColumns = Object.keys(firstRow)

    // Find coordinate columns
    const latColumns = allColumns.filter(col =>
        LAT_COLUMNS.some(lat => col.toLowerCase().includes(lat))
    )
    const lonColumns = allColumns.filter(col =>
        LON_COLUMNS.some(lon => col.toLowerCase().includes(lon))
    )

    // Filter available parameters
    const availableParameters = allColumns.filter(col => {
        const colLower = col.toLowerCase()

        if (EXCLUDE_KEYWORDS.some(keyword => colLower.includes(keyword))) {
            return false
        }

        if (LAT_COLUMNS.some(lat => colLower === lat || colLower.includes('latitude')) ||
            LON_COLUMNS.some(lon => colLower === lon || colLower.includes('longitude'))) {
            return false
        }

        // Check for numeric data
        const values = data.slice(0, 20).map((row: any) => row[col])
        const validNumbers = values.filter((v: any) => {
            if (v === null || v === undefined || v === '') return false
            const num = parseFloat(v)
            return !isNaN(num) && isFinite(num)
        })

        return validNumbers.length / values.length > 0.3
    })

    // Get sample data
    const sampleData = data.slice(0, 5)

    return NextResponse.json({
        success: true,
        sheetNames,
        columns: allColumns,
        availableParameters,
        latColumns,
        lonColumns,
        rowCount: data.length,
        sampleData,
        source: 'nodejs'
    })
}
