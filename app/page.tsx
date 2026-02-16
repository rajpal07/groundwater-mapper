import Link from 'next/link'
import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { redirect } from 'next/navigation'

export default async function HomePage() {
    const session = await getServerSession(authOptions)

    if (session) {
        redirect('/dashboard')
    }

    return (
        <div className="min-h-screen">
            {/* Header */}
            <header className="fixed top-0 left-0 right-0 bg-white/90 backdrop-blur-md z-50 border-b border-gray-100">
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary rounded-lg flex items-center justify-center">
                            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                            </svg>
                        </div>
                        <span className="text-xl font-bold text-primary-dark">Groundwater Mapper</span>
                    </div>
                    <nav className="hidden md:flex items-center gap-8">
                        <Link href="#features" className="text-gray-600 hover:text-primary transition-colors">Features</Link>
                        <Link href="#how-it-works" className="text-gray-600 hover:text-primary transition-colors">How it Works</Link>
                        <Link href="/auth/signin" className="text-primary hover:text-primary-dark transition-colors">Sign In</Link>
                        <Link href="/auth/signin" className="btn-primary">
                            Get Started
                        </Link>
                    </nav>
                </div>
            </header>

            {/* Hero Section */}
            <section className="pt-32 pb-20 bg-gradient-to-br from-primary-light via-white to-primary-light">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid lg:grid-cols-2 gap-12 items-center">
                        <div className="space-y-8">
                            <h1 className="text-5xl lg:text-6xl font-bold text-primary-dark leading-tight">
                                Generate Interactive Groundwater Maps
                            </h1>
                            <p className="text-xl text-gray-600 leading-relaxed">
                                Upload your Excel data and instantly create professional contour maps with aquifer analysis,
                                flow direction arrows, and export-ready HTML outputs.
                            </p>
                            <div className="flex flex-wrap gap-4">
                                <Link href="/auth/signin" className="btn-primary text-lg px-8 py-4">
                                    Start Mapping Free
                                </Link>
                                <button className="btn-outline text-lg px-8 py-4">
                                    Watch Demo
                                </button>
                            </div>
                            <div className="flex items-center gap-6 pt-4">
                                <div className="flex -space-x-2">
                                    {[1, 2, 3].map((i) => (
                                        <div key={i} className="w-10 h-10 rounded-full bg-gray-300 border-2 border-white" />
                                    ))}
                                </div>
                                <span className="text-gray-600">Trusted by 500+ environmental consultants</span>
                            </div>
                        </div>
                        <div className="relative">
                            <div className="bg-white rounded-2xl shadow-2xl p-2">
                                <div className="bg-gray-100 rounded-xl overflow-hidden aspect-video relative">
                                    <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-primary-dark/20" />
                                    <div className="absolute bottom-4 left-4 right-4 bg-white/90 backdrop-blur rounded-xl p-4">
                                        <div className="flex items-center gap-3">
                                            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                                            <span className="text-sm font-medium">Processing Complete</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" className="py-20 bg-white">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl font-bold text-primary-dark mb-4">Powerful Features</h2>
                        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
                            Everything you need to create professional groundwater maps
                        </p>
                    </div>
                    <div className="grid md:grid-cols-3 gap-8">
                        {[
                            {
                                icon: '📊',
                                title: 'AI-Powered Data Extraction',
                                description: 'Automatically parse complex Excel files with multiple sheets using LlamaParse AI'
                            },
                            {
                                icon: '🗺️',
                                title: 'Interactive Maps',
                                description: 'Generate beautiful contour maps with flow direction arrows and well markers'
                            },
                            {
                                icon: '🔄',
                                title: 'Aquifer Analysis',
                                description: 'Automatically detect and separate multiple aquifer layers from your data'
                            },
                            {
                                icon: '📍',
                                title: 'UTM Zone Detection',
                                description: 'Smart Australian coordinate system detection for accurate mapping'
                            },
                            {
                                icon: '🎨',
                                title: 'Custom Color Schemes',
                                description: 'Choose from multiple colormaps to best represent your data'
                            },
                            {
                                icon: '💾',
                                title: 'Project Management',
                                description: 'Save maps to projects and access them anytime from your dashboard'
                            }
                        ].map((feature, i) => (
                            <div key={i} className="card text-center">
                                <div className="text-5xl mb-4">{feature.icon}</div>
                                <h3 className="text-xl font-bold text-primary-dark mb-3">{feature.title}</h3>
                                <p className="text-gray-600">{feature.description}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* How It Works */}
            <section id="how-it-works" className="py-20 bg-gray-50">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl font-bold text-primary-dark mb-4">How It Works</h2>
                        <p className="text-xl text-gray-600">Three simple steps to generate your map</p>
                    </div>
                    <div className="grid md:grid-cols-3 gap-8">
                        {[
                            { step: '1', title: 'Upload Excel', description: 'Upload your groundwater data file in Excel format' },
                            { step: '2', title: 'AI Processing', description: 'Our AI automatically extracts and processes your data' },
                            { step: '3', title: 'Download Map', description: 'Get your interactive HTML map ready for reports' }
                        ].map((item, i) => (
                            <div key={i} className="relative">
                                <div className="w-16 h-16 bg-primary rounded-full flex items-center justify-center text-white text-2xl font-bold mb-6">
                                    {item.step}
                                </div>
                                <h3 className="text-xl font-bold text-primary-dark mb-2">{item.title}</h3>
                                <p className="text-gray-600">{item.description}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="py-20 bg-primary-dark text-white">
                <div className="max-w-4xl mx-auto px-6 text-center">
                    <h2 className="text-4xl font-bold mb-6">Ready to Start Mapping?</h2>
                    <p className="text-xl mb-8 opacity-90">Join hundreds of environmental professionals using Groundwater Mapper Pro</p>
                    <Link href="/auth/signin" className="inline-block bg-white text-primary-dark px-8 py-4 rounded-lg font-bold text-lg hover:bg-gray-100 transition-colors">
                        Get Started Free
                    </Link>
                </div>
            </section>

            {/* Footer */}
            <footer className="bg-gray-900 text-white py-12">
                <div className="max-w-7xl mx-auto px-6">
                    <div className="grid md:grid-cols-4 gap-8">
                        <div>
                            <div className="flex items-center gap-3 mb-4">
                                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                                    </svg>
                                </div>
                                <span className="text-lg font-bold">Groundwater Mapper</span>
                            </div>
                            <p className="text-gray-400 text-sm">Professional groundwater mapping for environmental consultants</p>
                        </div>
                        <div>
                            <h4 className="font-bold mb-4">Product</h4>
                            <ul className="space-y-2 text-gray-400">
                                <li><a href="#" className="hover:text-white">Features</a></li>
                                <li><a href="#" className="hover:text-white">Pricing</a></li>
                                <li><a href="#" className="hover:text-white">Documentation</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-bold mb-4">Company</h4>
                            <ul className="space-y-2 text-gray-400">
                                <li><a href="#" className="hover:text-white">About</a></li>
                                <li><a href="#" className="hover:text-white">Contact</a></li>
                                <li><a href="#" className="hover:text-white">Privacy</a></li>
                            </ul>
                        </div>
                        <div>
                            <h4 className="font-bold mb-4">Support</h4>
                            <ul className="space-y-2 text-gray-400">
                                <li><a href="#" className="hover:text-white">Help Center</a></li>
                                <li><a href="#" className="hover:text-white">Terms of Service</a></li>
                                <li><a href="#" className="hover:text-white">Status</a></li>
                            </ul>
                        </div>
                    </div>
                    <div className="border-t border-gray-800 mt-8 pt-8 text-center text-gray-400">
                        © {new Date().getFullYear()} Groundwater Mapper Pro. All rights reserved.
                    </div>
                </div>
            </footer>
        </div>
    )
}
