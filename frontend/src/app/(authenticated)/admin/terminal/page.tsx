'use client'

import { useState, useRef, useEffect } from 'react'
import { apiClient } from '@/lib/api-client'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Terminal as TerminalIcon, Play, Trash2, Copy, Download } from 'lucide-react'

interface CommandHistory {
  id: number
  command: string
  output: string
  timestamp: Date
  status: 'success' | 'error'
}

export default function Terminal() {
  const [command, setCommand] = useState('')
  const [history, setHistory] = useState<CommandHistory[]>([])
  const [executing, setExecuting] = useState(false)
  const terminalRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const predefinedCommands = [
    { label: 'Create Admin User', command: 'python -m backend.scripts.create_admin' },
    { label: 'Run Tests', command: 'pytest backend/tests/' },
    { label: 'Check Database', command: 'python -c "from backend.core.database import engine; print(engine.url)"' },
    { label: 'Export Statistics', command: 'python -m backend.scripts.export_stats' },
    { label: 'Clear Cache', command: 'python -m backend.scripts.clear_cache' },
    { label: 'Backup Database', command: 'python -m backend.scripts.backup_db' },
  ]

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [history])

  const executeCommand = async (cmd: string) => {
    if (!cmd.trim()) return

    setExecuting(true)
    const startTime = Date.now()

    try {
      // In a real implementation, this would call a backend endpoint
      // that safely executes commands in a sandboxed environment
      const response = await apiClient.post('/api/admin/terminal/execute', {
        command: cmd
      })

      const newEntry: CommandHistory = {
        id: Date.now(),
        command: cmd,
        output: response.data.output || 'Command executed successfully',
        timestamp: new Date(),
        status: 'success'
      }

      setHistory([...history, newEntry])
    } catch (error: any) {
      const newEntry: CommandHistory = {
        id: Date.now(),
        command: cmd,
        output: error.response?.data?.detail || 'Error executing command',
        timestamp: new Date(),
        status: 'error'
      }

      setHistory([...history, newEntry])
    } finally {
      setExecuting(false)
      setCommand('')
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      executeCommand(command)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const exportHistory = () => {
    const content = history.map(h => 
      `[${h.timestamp.toISOString()}] $ ${h.command}\n${h.output}\n`
    ).join('\n')

    const blob = new Blob([content], { type: 'text/plain' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `terminal_history_${new Date().toISOString().split('T')[0]}.txt`
    a.click()
  }

  const clearHistory = () => {
    if (confirm('Are you sure you want to clear the terminal history?')) {
      setHistory([])
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Admin Terminal</h1>
          <p className="text-gray-600 mt-1">Execute administrative commands safely</p>
        </div>
        <div className="flex space-x-3">
          <Button
            onClick={exportHistory}
            variant="outline"
            size="sm"
            className="flex items-center space-x-2"
          >
            <Download className="w-4 h-4" />
            <span>Export</span>
          </Button>
          <Button
            onClick={clearHistory}
            variant="outline"
            size="sm"
            className="flex items-center space-x-2"
          >
            <Trash2 className="w-4 h-4" />
            <span>Clear</span>
          </Button>
        </div>
      </div>

      {/* Quick Commands */}
      <Card className="p-4 mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Quick Commands</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {predefinedCommands.map((cmd, index) => (
            <Button
              key={index}
              variant="outline"
              size="sm"
              onClick={() => setCommand(cmd.command)}
              className="justify-start"
            >
              <Play className="w-3 h-3 mr-2" />
              {cmd.label}
            </Button>
          ))}
        </div>
      </Card>

      {/* Terminal */}
      <Card className="bg-gray-900 text-gray-100 p-6">
        <div className="flex items-center mb-4">
          <TerminalIcon className="w-5 h-5 mr-2" />
          <span className="font-mono text-sm">Admin Terminal</span>
        </div>

        <div
          ref={terminalRef}
          className="font-mono text-sm space-y-4 max-h-96 overflow-y-auto mb-4"
        >
          {history.length === 0 && (
            <div className="text-gray-500">
              Welcome to the admin terminal. Type a command and press Enter to execute.
            </div>
          )}
          
          {history.map((entry) => (
            <div key={entry.id} className="group">
              <div className="flex items-start">
                <span className="text-green-400 mr-2">$</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-100">{entry.command}</span>
                    <button
                      onClick={() => copyToClipboard(entry.command)}
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <Copy className="w-3 h-3 text-gray-500 hover:text-gray-300" />
                    </button>
                  </div>
                  <pre className={`mt-2 whitespace-pre-wrap ${
                    entry.status === 'error' ? 'text-red-400' : 'text-gray-300'
                  }`}>
                    {entry.output}
                  </pre>
                  <span className="text-xs text-gray-600">
                    {entry.timestamp.toLocaleTimeString()}
                  </span>
                </div>
              </div>
            </div>
          ))}

          {executing && (
            <div className="flex items-center text-yellow-400">
              <span className="mr-2">$</span>
              <span>{command}</span>
              <span className="ml-2 animate-pulse">_</span>
            </div>
          )}
        </div>

        <div className="flex items-center border-t border-gray-800 pt-4">
          <span className="text-green-400 mr-2">$</span>
          <input
            ref={inputRef}
            type="text"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={executing}
            placeholder="Enter command..."
            className="flex-1 bg-transparent outline-none text-gray-100 placeholder-gray-600"
          />
          <Button
            onClick={() => executeCommand(command)}
            disabled={executing || !command.trim()}
            size="sm"
            className="ml-3"
          >
            <Play className="w-4 h-4" />
          </Button>
        </div>
      </Card>

      {/* Warning */}
      <Card className="mt-6 p-4 bg-yellow-50 border-yellow-200">
        <div className="flex items-start space-x-3">
          <TerminalIcon className="w-5 h-5 text-yellow-600 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-yellow-800">Security Notice</p>
            <p className="text-sm text-yellow-700 mt-1">
              Commands are executed in a sandboxed environment with limited permissions. 
              Only pre-approved administrative commands are allowed for security reasons.
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}