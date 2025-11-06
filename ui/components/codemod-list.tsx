'use client';

import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { cn, filterBySearch } from '@/lib/utils';
import { CodemodMetadata, ProgrammingLanguage } from '@/types';

interface CodemodListProps {
  onSelectCodemod: (label: string) => void;
  selectedLabel: string | null;
}

// Mock data for demonstration (replace with actual API call)
const mockCodemods: CodemodMetadata[] = [
  {
    label: 'python2_to_python3',
    name: 'Python 2 to Python 3',
    description: 'Migrate Python 2 code to Python 3',
    category: 'Migration',
    tags: ['python', 'migration', 'modernization'],
    language: ProgrammingLanguage.PYTHON,
  },
  {
    label: 'unittest_to_pytest',
    name: 'unittest to pytest',
    description: 'Convert unittest tests to pytest',
    category: 'Refactoring',
    tags: ['python', 'testing', 'pytest'],
    language: ProgrammingLanguage.PYTHON,
  },
  {
    label: 'flask_to_fastapi_migration',
    name: 'Flask to FastAPI',
    description: 'Migrate Flask applications to FastAPI',
    category: 'Migration',
    tags: ['python', 'web', 'fastapi'],
    language: ProgrammingLanguage.PYTHON,
  },
  {
    label: 'delete_dead_code',
    name: 'Delete Dead Code',
    description: 'Remove unused code and imports',
    category: 'Code Quality',
    tags: ['cleanup', 'optimization'],
    language: ProgrammingLanguage.PYTHON,
  },
  {
    label: 'add_type_annotations',
    name: 'Add Type Annotations',
    description: 'Add missing type hints to functions',
    category: 'Code Quality',
    tags: ['typing', 'types', 'modernization'],
    language: ProgrammingLanguage.PYTHON,
  },
];

export function CodemodList({ onSelectCodemod, selectedLabel }: CodemodListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // In production, this would fetch from the API
  const codemods = mockCodemods;

  const filteredCodemods = useMemo(() => {
    let filtered = codemods;

    if (searchQuery) {
      filtered = filterBySearch(filtered, searchQuery, ['name', 'description', 'tags']);
    }

    if (selectedCategory) {
      filtered = filtered.filter(c => c.category === selectedCategory);
    }

    return filtered;
  }, [codemods, searchQuery, selectedCategory]);

  const categories = useMemo(() => {
    return Array.from(new Set(codemods.map(c => c.category)));
  }, [codemods]);

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Codemods</CardTitle>
        <CardDescription>
          Browse and search available code transformations
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search codemods..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8"
            aria-label="Search codemods"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedCategory(null)}
            className={cn(
              'text-xs px-3 py-1 rounded-full border transition-colors',
              !selectedCategory
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-accent'
            )}
          >
            All
          </button>
          {categories.map(category => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={cn(
                'text-xs px-3 py-1 rounded-full border transition-colors',
                selectedCategory === category
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent'
              )}
            >
              {category}
            </button>
          ))}
        </div>

        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {filteredCodemods.length === 0 ? (
            <div className="empty-state py-8">
              <p>No codemods found</p>
            </div>
          ) : (
            filteredCodemods.map(codemod => (
              <button
                key={codemod.label}
                onClick={() => onSelectCodemod(codemod.label)}
                className={cn(
                  'w-full text-left p-3 rounded-md border transition-all',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  selectedLabel === codemod.label
                    ? 'bg-accent border-primary'
                    : 'hover:bg-accent/50'
                )}
                aria-pressed={selectedLabel === codemod.label}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium truncate">{codemod.name}</h4>
                    <p className="text-sm text-muted-foreground line-clamp-2">
                      {codemod.description}
                    </p>
                  </div>
                  <Badge variant="secondary">{codemod.category}</Badge>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {codemod.tags.map(tag => (
                    <Badge key={tag} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </button>
            ))
          )}
        </div>

        <div className="pt-2 border-t text-sm text-muted-foreground">
          Showing {filteredCodemods.length} of {codemods.length} codemods
        </div>
      </CardContent>
    </Card>
  );
}
