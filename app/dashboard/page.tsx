'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/lib/auth-context'

interface Project {
  id: string
  name: string
  description: string
  createdAt: string
  mapCount: number
}

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchProjects = async () => {
      if (!user) return

      try {
        const token = await user.getIdToken()
        const response = await fetch('/api/projects', {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })

        if (!response.ok) {
          throw new Error('Failed to fetch projects')
        }

        const data = await response.json()
        setProjects(data.projects || [])
      } catch (err) {
        console.error('Error fetching projects:', err)
        setError('Failed to load projects')
      } finally {
        setLoading(false)
      }
    }

    if (user) {
      fetchProjects()
    }
  }, [user])

  if (authLoading || loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-10 h-10 border-4 border-gray-200 border-t-primary rounded-full animate-spin"></div>
        <p className="text-gray-600">Loading your dashboard...</p>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="text-center py-12 px-4 sm:px-6 lg:px-8 bg-gradient-to-r from-primary to-primary-dark rounded-2xl text-white mb-8">
        <h1 className="text-3xl font-bold mb-3">Welcome to Groundwater Mapper</h1>
        <p className="opacity-90 mb-6">Create and manage your groundwater mapping projects</p>

        <Link href="/dashboard/projects" className="inline-flex items-center gap-2 px-6 py-3 bg-white text-primary font-semibold rounded-lg hover:translate-y-[-2px] transition-transform">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Create New Project
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg mb-8">
          {error}
        </div>
      )}

      <div className="projects-section">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Your Projects</h2>

        {projects.length === 0 ? (
          <div className="text-center py-16 px-4 bg-gray-50 rounded-xl">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="1" className="mx-auto mb-4">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            </svg>
            <h3 className="text-lg font-semibold text-gray-800 mb-2">No projects yet</h3>
            <p className="text-gray-600 mb-6">Create your first project to start mapping groundwater data</p>
            <Link href="/dashboard/projects" className="inline-block px-6 py-2 border-2 border-primary text-primary rounded-lg font-medium hover:bg-primary hover:text-white transition-colors">
              Create Project
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <Link key={project.id} href={`/dashboard/projects/${project.id}`} className="flex gap-4 p-6 bg-white border border-gray-200 rounded-xl hover:border-primary hover:shadow-lg hover:shadow-primary/10 transition-all">
                <div className="w-12 h-12 flex items-center justify-center bg-primary-light rounded-lg text-primary">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                    <circle cx="12" cy="10" r="3"></circle>
                  </svg>
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-800 mb-1">{project.name}</h3>
                  <p className="text-gray-600 text-sm mb-2">{project.description || 'No description'}</p>
                  <span className="text-xs text-gray-500">
                    {project.mapCount || 0} maps · {new Date(project.createdAt).toLocaleDateString()}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
