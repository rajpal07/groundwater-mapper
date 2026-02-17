import { NextResponse } from 'next/server'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import * as XLSX from 'xlsx'

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
