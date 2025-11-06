'use client';

import { useState } from 'react';
import { Book, Search, ExternalLink } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';

export function DocumentationPanel() {
  const [searchQuery, setSearchQuery] = useState('');

  const docSections = [
    {
      title: 'Getting Started',
      description: 'Learn the basics of Graph-Sitter and how to create your first codemod',
      topics: ['Installation', 'Quick Start', 'Basic Concepts'],
    },
    {
      title: 'Codemod Development',
      description: 'Deep dive into creating powerful codemods',
      topics: ['Writing Codemods', 'Symbol Resolution', 'Type Inference'],
    },
    {
      title: 'API Reference',
      description: 'Complete API documentation for all classes and methods',
      topics: ['Codebase API', 'Symbol Classes', 'Runner API'],
    },
    {
      title: 'Examples',
      description: 'Learn from real-world codemod examples',
      topics: ['Migration Codemods', 'Refactoring', 'Code Quality'],
    },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Documentation</CardTitle>
          <CardDescription>
            Browse comprehensive documentation for Graph-Sitter
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="relative">
              <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search documentation..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
                aria-label="Search documentation"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {docSections.map((section) => (
                <Card key={section.title} className="card-hover">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <Book className="h-5 w-5 text-primary" />
                      <ExternalLink className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <CardTitle className="text-lg">{section.title}</CardTitle>
                    <CardDescription>{section.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {section.topics.map((topic) => (
                        <Badge key={topic} variant="secondary">
                          {topic}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="border-t pt-4 mt-6">
              <h3 className="font-semibold mb-3">Quick Links</h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <a
                  href="https://docs.graphsitter.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-2 rounded-md hover:bg-accent transition-colors"
                >
                  <ExternalLink className="h-4 w-4" />
                  <span className="text-sm">Full Documentation</span>
                </a>
                <a
                  href="https://github.com/graphsitter/graphsitter"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-2 rounded-md hover:bg-accent transition-colors"
                >
                  <ExternalLink className="h-4 w-4" />
                  <span className="text-sm">GitHub Repository</span>
                </a>
                <a
                  href="https://github.com/graphsitter/graphsitter/issues"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-2 rounded-md hover:bg-accent transition-colors"
                >
                  <ExternalLink className="h-4 w-4" />
                  <span className="text-sm">Report Issues</span>
                </a>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
