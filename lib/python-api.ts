/**
 * Python API Client
 * 
 * A shared client for communicating with the FastAPI Python backend.
 * This client handles authentication, error handling, and provides
 * type-safe methods for all API endpoints.
 */

// Python microservice URL - set in environment variables
// For local development: NEXT_PUBLIC_PYTHON_SERVICE_URL=http://localhost:5000
// For production: NEXT_PUBLIC_PYTHON_SERVICE_URL=https://groundwater-mapper.onrender.com
const PYTHON_SERVICE_URL = process.env.NEXT_PUBLIC_PYTHON_SERVICE_URL

// Vercel has a hard limit of 4.5MB for serverless function request bodies
const VERCEL_LIMIT = 4.5 * 1024 * 1024 // 4.5MB in bytes

/**
 * Response when file is too large for Vercel
 */
export interface LargeFileResponse {
    error: string
    pythonServiceUrl: string | null
    fileSize: number
    limit: number
    requiresDirectUpload: boolean
}

/**
 * Check if Python service is configured
 */
export function isPythonServiceConfigured(): boolean {
    return !!PYTHON_SERVICE_URL
}

/**
 * Get the Python service URL
 */
export function getPythonServiceUrl(): string | null {
    return PYTHON_SERVICE_URL || null
}

/**
 * Get Vercel file size limit
 */
export function getVercelLimit(): number {
    return VERCEL_LIMIT
}

/**
 * Check if file size exceeds Vercel limit
 */
export function exceedsVercelLimit(fileSize: number): boolean {
    return fileSize > VERCEL_LIMIT
}

/**
 * API Error class for handling errors from the Python service
 */
export class PythonApiError extends Error {
    status: number
    details?: any

    constructor(message: string, status: number, details?: any) {
        super(message)
        this.name = 'PythonApiError'
        this.status = status
        this.details = details
    }
}

/**
 * Options for API requests
 */
interface RequestOptions {
    token?: string
    method?: 'GET' | 'POST' | 'DELETE'
    body?: BodyInit
    headers?: Record<string, string>
}

/**
 * Make an authenticated request to the Python API
 */
async function makeRequest<T>(
    endpoint: string,
    options: RequestOptions = {}
): Promise<T> {
    const { token, method = 'GET', body, headers = {} } = options

    if (!PYTHON_SERVICE_URL) {
        throw new PythonApiError('Python service not configured', 503)
    }

    const requestHeaders: Record<string, string> = {
        ...headers,
    }

    if (token) {
        requestHeaders['Authorization'] = `Bearer ${token}`
    }

    const baseUrl = PYTHON_SERVICE_URL.replace(/\/$/, '')
    const response = await fetch(`${baseUrl}${endpoint}`, {
        method,
        headers: requestHeaders,
        body,
    })

    if (!response.ok) {
        let errorMessage = `API Error: ${response.status}`
        let details = null

        try {
            const errorData = await response.json()
            errorMessage = errorData.detail || errorData.error || errorMessage
            details = errorData
        } catch {
            // Response wasn't JSON, use status text
            errorMessage = response.statusText || errorMessage
        }

        throw new PythonApiError(errorMessage, response.status, details)
    }

    return response.json()
}

// ============================================
// Health Endpoints
// ============================================

export interface HealthResponse {
    status: string
    version: string
    services: {
        llamaparse: boolean
        earth_engine: boolean
    }
}

/**
 * Check Python API health
 */
export async function checkHealth(): Promise<HealthResponse> {
    return makeRequest<HealthResponse>('/health')
}

// ============================================
// Preview Endpoints
// ============================================

export interface PreviewResponse {
    success: boolean
    sheets?: string[]
    sheet_names?: string[]
    columns: string[]
    numeric_columns: string[]
    row_count: number
    preview: Record<string, any>[]
    parse_method?: string
    coordinate_system?: {
        type: string
        utm_zone?: number
        utm_hemisphere?: string
    }
}

/**
 * Preview an Excel file
 * @param file The Excel file to preview
 * @param token Firebase ID token for authentication
 * @param useLlamaParse Whether to use LlamaParse for parsing
 */
export async function previewExcel(
    file: File,
    token: string,
    useLlamaParse: boolean = true,
    sheetName?: string
): Promise<PreviewResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('use_llamaparse', String(useLlamaParse))

    if (sheetName) {
        formData.append('sheet_name', sheetName)
    }

    return makeRequest<PreviewResponse>('/preview', {
        method: 'POST',
        token,
        body: formData,
    })
}

/**
 * Preview an Excel file from buffer (for server-side use)
 */
export async function previewExcelFromBuffer(
    buffer: Buffer,
    filename: string,
    token: string,
    useLlamaParse: boolean = true,
    sheetName?: string
): Promise<PreviewResponse> {
    const formData = new FormData()
    // Convert Buffer to Blob - use buffer as ArrayBuffer with type assertion
    const arrayBuffer = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength) as ArrayBuffer
    formData.append('file', new Blob([arrayBuffer]), filename)
    formData.append('use_llamaparse', String(useLlamaParse))

    if (sheetName) {
        formData.append('sheet_name', sheetName)
    }

    return makeRequest<PreviewResponse>('/preview', {
        method: 'POST',
        token,
        body: formData,
    })
}

// ============================================
// Process Endpoints
// ============================================

export interface ProcessRequest {
    file: File
    parameter: string
    colormap?: string
    interpolation_method?: 'linear' | 'cubic' | 'nearest'
    sheet_name?: string
}

export interface ProcessResponse {
    success: boolean
    map_html: string
    bounds?: {
        min_lat: number
        max_lat: number
        min_lon: number
        max_lon: number
    } | null
    contour_data: {
        levels: number[]
        colors: string[]
    }
    statistics: {
        min: number
        max: number
        mean: number
        std: number
        count: number
    }
    coordinate_system: {
        type: string
        utm_zone?: number
        utm_hemisphere?: string
    }
    parse_method?: string
}

/**
 * Process an Excel file and generate a contour map
 */
export async function processExcel(
    file: File,
    parameter: string,
    token: string,
    options: {
        colormap?: string
        interpolation_method?: 'linear' | 'cubic' | 'nearest'
        sheet_name?: string
    } = {}
): Promise<ProcessResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('parameter', parameter)

    if (options.colormap) {
        formData.append('colormap', options.colormap)
    }
    if (options.interpolation_method) {
        formData.append('interpolation_method', options.interpolation_method)
    }
    if (options.sheet_name) {
        formData.append('sheet_name', options.sheet_name)
    }

    return makeRequest<ProcessResponse>('/process', {
        method: 'POST',
        token,
        body: formData,
    })
}

/**
 * Process an Excel file from buffer (for server-side use)
 */
export async function processExcelFromBuffer(
    buffer: Buffer,
    filename: string,
    parameter: string,
    token: string,
    options: {
        colormap?: string
        interpolation_method?: 'linear' | 'cubic' | 'nearest'
        sheet_name?: string
    } = {}
): Promise<ProcessResponse> {
    const formData = new FormData()
    // Convert Buffer to Blob - use buffer as ArrayBuffer with type assertion
    const arrayBuffer = buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength) as ArrayBuffer
    formData.append('file', new Blob([arrayBuffer]), filename)
    formData.append('parameter', parameter)

    if (options.colormap) {
        formData.append('colormap', options.colormap)
    }
    if (options.interpolation_method) {
        formData.append('interpolation_method', options.interpolation_method)
    }
    if (options.sheet_name) {
        formData.append('sheet_name', options.sheet_name)
    }

    return makeRequest<ProcessResponse>('/process', {
        method: 'POST',
        token,
        body: formData,
    })
}

// ============================================
// Multi-Layer Process Endpoints
// ============================================

export interface MultiLayerProcessRequest {
    file: File
    parameters: string[]
    colormap?: string
    interpolation_method?: 'linear' | 'cubic' | 'nearest'
    sheet_name?: string
}

export interface AquiferLayer {
    name: string
    min_depth: number
    max_depth: number
    parameter: string
    color: string
}

export interface MultiLayerProcessResponse {
    success: boolean
    map_html: string
    bounds?: {
        min_lat: number
        max_lat: number
        min_lon: number
        max_lon: number
    } | null
    layers: AquiferLayer[]
    statistics: Record<string, {
        min: number
        max: number
        mean: number
        std: number
        count: number
    }>
}

/**
 * Process multiple parameters for multi-layer map
 */
export async function processMultiLayer(
    file: File,
    parameters: string[],
    token: string,
    options: {
        colormap?: string
        interpolation_method?: 'linear' | 'cubic' | 'nearest'
        sheet_name?: string
    } = {}
): Promise<MultiLayerProcessResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('parameters', JSON.stringify(parameters))

    if (options.colormap) {
        formData.append('colormap', options.colormap)
    }
    if (options.interpolation_method) {
        formData.append('interpolation_method', options.interpolation_method)
    }
    if (options.sheet_name) {
        formData.append('sheet_name', options.sheet_name)
    }

    return makeRequest<MultiLayerProcessResponse>('/process/multi-layer', {
        method: 'POST',
        token,
        body: formData,
    })
}

// ============================================
// Smart Export Endpoints
// ============================================

export interface SmartExportRequest {
    file: File
    parameter: string
    thresholds?: number[]
    sheet_name?: string
}

export interface SmartExportResponse {
    success: boolean
    file_data: string  // Base64 encoded Excel file
    filename: string
    statistics: {
        min: number
        max: number
        mean: number
        std: number
        count: number
        below_threshold: number
        above_threshold: number
    }
}

/**
 * Generate a smart Excel export with conditional formatting
 */
export async function smartExport(
    file: File,
    parameter: string,
    token: string,
    options: {
        thresholds?: number[]
        sheet_name?: string
    } = {}
): Promise<SmartExportResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('parameter', parameter)

    if (options.thresholds) {
        formData.append('thresholds', JSON.stringify(options.thresholds))
    }
    if (options.sheet_name) {
        formData.append('sheet_name', options.sheet_name)
    }

    return makeRequest<SmartExportResponse>('/export/smart-excel', {
        method: 'POST',
        token,
        body: formData,
    })
}

// ============================================
// Export client for direct frontend use
// ============================================

export const pythonApi = {
    // Configuration
    isConfigured: isPythonServiceConfigured,
    getUrl: getPythonServiceUrl,
    getVercelLimit,
    exceedsVercelLimit,

    // Health
    checkHealth,

    // Preview
    previewExcel,
    previewExcelFromBuffer,

    // Process
    processExcel,
    processExcelFromBuffer,
    processMultiLayer,

    // Export
    smartExport,

    // Error handling
    PythonApiError,
}

export default pythonApi
