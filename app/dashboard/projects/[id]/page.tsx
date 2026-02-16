'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'

interface Project {
  id: string
  name: string
  description: string
  createdAt: string
}

interface Map {
  id: string
  name: string
  status: 'pending' | 'processing' | 'complete' | 'failed'
  createdAt: string
  processedAt: string
}

export default function ProjectDetailPage() {
  const { id } = useParams()
  const router = useRouter()
  const { user } = useAuth()
  const [project, setProject] = useState<Project | null>(null)
  const [maps, setMaps] = useState<Map[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const token = await user!.getIdToken()
        const response = await fetch(`/api/projects/${id}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Project not found')
          }
          throw new Error('Failed to fetch project')
        }

        const data = await response.json()
        setProject(data.project)
        setMaps(data.maps || [])
      } catch (err) {
        console.error('Error fetching project:', err)
        setError(err instanceof Error ? err.message : 'Failed to fetch project')
      } finally {
        setLoading(false)
      }
    }

    if (user) {
      fetchProject()
    }
  }, [user, id])

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this project?')) {
      return
    }

    try {
      const token = await user!.getIdToken()
      const response = await fetch(`/api/projects/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.error || 'Failed to delete project')
      }

      router.push('/dashboard')
    } catch (err) {
      console.error('Error deleting project:', err)
      setError(err instanceof Error ? err.message : 'Failed to delete project')
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-10 h-10 border-4 border-gray-200 border-t-primary rounded-full animate-spin"></div>
        <p className="text-gray-600">Loading project...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-8">
          {error}
        </div>
        <Link href="/dashboard" className="text-primary hover:text-primary-dark font-medium">
          ← Back to Dashboard
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex justify-between items-start mb-8">
        <div>
          <Link href="/dashboard" className="text-primary hover:text-primary-dark font-medium mb-4 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">{project?.name}</h1>
          {project?.description && (
            <p className="text-gray-600 mb-4">{project.description}</p>
          )}
          <p className="text-sm text-gray-500">
            Created on {new Date(project?.createdAt || '').toLocaleDateString()}
          </p>
        </div>
        <button
          onClick={handleDelete}
          className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors text-sm"
        >
          Delete Project
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-8">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">Maps</h2>
            <Link href={`/dashboard/projects/${id}/maps/new`} className="px-6 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors flex items-center gap-2">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
              Create Map
            </Link>
          </div>

          {maps.length === 0 ? (
            <div className="text-center py-12 px-4">
              <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1" className="mx-auto mb-4">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              </svg>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">No maps yet</h3>
              <p className="text-gray-600 mb-6">Create your first map to start visualizing groundwater data</p>
              <Link href={`/dashboard/projects/${id}/maps/new`} className="inline-block px-6 py-2 border-2 border-primary text-primary rounded-lg font-medium hover:bg-primary hover:text-white transition-colors">
                Create Map
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 font-semibold text-gray-800">Map Name</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-800">Status</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-800">Created</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-800">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {maps.map((map) => (
                    <tr key={map.id} className="border-b border-gray-100">
                      <td className="py-4 px-4">
                        <Link href={`/dashboard/projects/${id}/maps/${map.id}`} className="text-primary hover:text-primary-dark font-medium">
                          {map.name}
                        </Link>
                      </td>
                      <td className="py-4 px-4">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${map.status === 'complete' ? 'bg-green-100 text-green-800' :
                            map.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                              map.status === 'failed' ? 'bg-red-100 text-red-800' :
                                'bg-yellow-100 text-yellow-800'
                          }`}>
                          {map.status.charAt(0).toUpperCase() + map.status.slice(1)}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-sm text-gray-500">
                        {new Date(map.createdAt).toLocaleDateString()}
                      </td>
                      <td className="py-4 px-4">
                        <Link href={`/dashboard/projects/${id}/maps/${map.id}`} className="px-3 py-1 bg-primary text-white rounded-lg hover:bg-primary-dark transition-colors text-sm">
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
