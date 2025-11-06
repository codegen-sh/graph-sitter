'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { File, Folder, ChevronRight, ChevronDown } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { cn } from '@/lib/utils';

export function RepositoryBrowser() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set(['/']));

  // Mock file tree data
  const fileTree = {
    '/': {
      'src': {
        'graph_sitter': {
          'core': {
            'codebase.py': null,
            'symbol.py': null,
          },
          'runner': {
            'sandbox': {
              'runner.py': null,
              'server.py': null,
            },
          },
        },
      },
      'tests': {
        'unit': {
          'test_codebase.py': null,
        },
      },
      'README.md': null,
      'pyproject.toml': null,
    },
  };

  const toggleDir = (path: string) => {
    const newExpanded = new Set(expandedDirs);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedDirs(newExpanded);
  };

  const renderFileTree = (node: any, path: string = '', level: number = 0) => {
    if (!node) return null;

    return Object.keys(node).map((key) => {
      const fullPath = `${path}/${key}`;
      const isDir = node[key] !== null;
      const isExpanded = expandedDirs.has(fullPath);
      const isSelected = selectedFile === fullPath;

      return (
        <div key={fullPath}>
          <button
            onClick={() => {
              if (isDir) {
                toggleDir(fullPath);
              } else {
                setSelectedFile(fullPath);
              }
            }}
            className={cn(
              'file-tree-item w-full',
              isSelected && 'bg-accent font-semibold'
            )}
            style={{ paddingLeft: `${level * 1.5 + 0.5}rem` }}
          >
            {isDir ? (
              <>
                {isExpanded ? (
                  <ChevronDown className="file-tree-icon" />
                ) : (
                  <ChevronRight className="file-tree-icon" />
                )}
                <Folder className="file-tree-icon text-blue-500" />
              </>
            ) : (
              <>
                <span className="w-4" />
                <File className="file-tree-icon text-muted-foreground" />
              </>
            )}
            <span className="flex-1 text-left truncate">{key}</span>
          </button>
          {isDir && isExpanded && renderFileTree(node[key], fullPath, level + 1)}
        </div>
      );
    });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle>File Browser</CardTitle>
          <CardDescription>Navigate repository files</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Input
              placeholder="Search files..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <div className="file-tree max-h-[600px] overflow-y-auto border rounded-md p-2">
              {renderFileTree(fileTree['/'])}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>File Preview</CardTitle>
          <CardDescription>
            {selectedFile || 'Select a file to preview'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {selectedFile ? (
            <div className="border rounded-md p-4 bg-muted/50">
              <div className="flex items-center gap-2 mb-4">
                <Badge variant="secondary">Python</Badge>
                <Badge variant="outline">1,234 lines</Badge>
              </div>
              <pre className="text-sm font-mono overflow-x-auto">
                <code>{`# File: ${selectedFile}\n\n# Content preview would go here...\n\nclass Example:\n    def __init__(self):\n        pass\n`}</code>
              </pre>
            </div>
          ) : (
            <div className="empty-state py-12">
              <File className="empty-state-icon" />
              <p>Select a file to view its contents</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
