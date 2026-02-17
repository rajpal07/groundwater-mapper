'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'

interface MapData {
    id: string
    name: string
    status: 'pending' | 'processing' | 'complete' | 'failed'
    dataPoints?: any[]
    createdAt: string
    processedAt?: string
}

export default function MapDetailPage() {
    const { id: projectId, mapId } = useParams()
    const router = useRouter()
    const { user } = useAuth()
    const [map, setMap] = useState<MapData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')

    useEffect(() => {
        const fetchMap = async () => {
            try {
                const token = await user!.getIdToken()
                const response = await fetch(`/api/projects/${projectId}/maps/${mapId}`, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                })

                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error('Map not found')
                    }
                    throw new Error('Failed to fetch map')
                }

                const data = await response.json()
                setMap(data.map)
            } catch (err) {
                console.error('Error fetching map:', err)
                setError(err instanceof Error ? err.message : 'Failed to fetch map')
            } finally {
                setLoading(false)
            }
        }

        if (user && projectId && mapId) {
            fetchMap()
        }
    }, [user, projectId, mapId])

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                <div className="w-10 h-10 border-4 border-gray-200 border-t-primary rounded-full animate-spin"></div>
                <p className="text-gray-600">Loading map...</p>
            </div>
        )
    }

    if (error) {
        return (
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-6">
                    {error}
                </div>
                <Link href={`/dashboard/projects/${projectId}`} className="text-primary hover:text-primary-dark font-medium">
                    ← Back to Project
                </Link>
            </div>
        )
    }

    return (
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Link
                href={`/dashboard/projects/${projectId}`}
                className="text-primary hover:text-primary-dark font-medium mb-6 inline-block"
            >
                ← Back to Project
            </Link>

            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-800 mb-2">{map?.name}</h1>
                <p className="text-gray-600">
                    Created on {map?.createdAt ? new Date(map.createdAt).toLocaleDateString() : 'N/A'}
                </p>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="p-6">
                    {map?.status === 'complete' ? (
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                                    Complete
                                </span>
                            </div>

                            {map.dataPoints && map.dataPoints.length > 0 ? (
                                <div>
                                    <h2 className="text-xl font-bold mb-4">Map Visualization</h2>
                                    <div className="bg-gray-50 rounded-lg p-4 min-h-[400px] flex items-center justify-center">
                                        <p className="text-gray-500">Map visualization will be displayed here</p>
                                    </div>
                                    <div className="mt-4 text-sm text-gray-600">
                                        <p>Total data points: {map.dataPoints.length}</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-12">
                                    <p className="text-gray-600">No data points found in this map</p>
                                </div>
                            )}
                        </div>
                    ) : map?.status === 'processing' ? (
                        <div className="text-center py-12">
                            <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-4"></div>
                            <h3 className="text-lg font-semibold text-gray-800 mb-2">Processing Data</h3>
                            <p className="text-gray-600">Your groundwater data is being processed...</p>
                        </div>
                    ) : map?.status === 'failed' ? (
                        <div className="text-center py-12">
                            <svg className="w-16 h-16 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                            <h3 className="text-lg font-semibold text-gray-800 mb-2">Processing Failed</h3>
                            <p className="text-gray-600">There was an error processing your data. Please try again.</p>
                        </div>
                    ) : (
                        <div className="text-center py-12">
                            <div className="w-16 h-16 border-4 border-gray-200 rounded-full mx-auto mb-4"></div>
                            <h3 className="text-lg font-semibold text-gray-800 mb-2">Pending</h3>
                            <p className="text-gray-600">Waiting for data to be processed...</p>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
