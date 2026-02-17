import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
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

export async function POST(request: Request): Promise<NextResponse> {
    try {
        const session = await getServerSession(authOptions)
        const userId = session?.user?.email

        if (!userId) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
        }

        const formData = await request.formData()
        const file = formData.get('file') as File

        if (!file) {
            return NextResponse.json({ error: 'No file provided' }, { status: 400 })
        }

        // If Python service URL is configured, use it
        if (PYTHON_SERVICE_URL) {
            try {
                // Convert file to base64 for Python service
                const buffer = Buffer.from(await file.arrayBuffer())
                const base64Content = buffer.toString('base64')

                // Forward to Python service
                const pythonFormData = new FormData()
                pythonFormData.append('file', new Blob([buffer]), file.name)
                pythonFormData.append('use_llamaparse', 'true')

                const pythonResponse = await fetch(`${PYTHON_SERVICE_URL}/preview`, {
                    method: 'POST',
                    body: pythonFormData,
                })

                if (pythonResponse.ok) {
                    const pythonData = await pythonResponse.json()
                    return NextResponse.json({
                        success: true,
                        columns: pythonData.columns,
                        availableParameters: pythonData.numeric_columns,
                        rowCount: pythonData.row_count,
                        sampleData: pythonData.preview,
                        source: 'python',
                        parse_method: pythonData.parse_method
                    })
                } else {
                    console.error('Python service error:', await pythonResponse.text())
                }
            } catch (pythonError) {
                console.error('Error calling Python service:', pythonError)
                // Fall through to Node.js implementation
            }
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
