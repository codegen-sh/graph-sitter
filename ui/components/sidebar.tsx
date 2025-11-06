'use client';

import {
  Code,
  FileText,
  FolderTree,
  Settings,
  BookOpen,
  History,
  GitCompare
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ViewType } from '@/types';

interface SidebarProps {
  currentView: ViewType;
  onViewChange: (view: ViewType) => void;
  isOpen: boolean;
}

const navItems = [
  {
    icon: Code,
    label: 'Codemods',
    view: ViewType.CODEMODS,
    description: 'Browse and execute codemods'
  },
  {
    icon: GitCompare,
    label: 'Diff Viewer',
    view: ViewType.DIFF,
    description: 'View code changes'
  },
  {
    icon: FolderTree,
    label: 'Repository',
    view: ViewType.REPOSITORY,
    description: 'Browse repository files'
  },
  {
    icon: History,
    label: 'History',
    view: ViewType.HISTORY,
    description: 'Execution history'
  },
  {
    icon: BookOpen,
    label: 'Documentation',
    view: ViewType.DOCUMENTATION,
    description: 'View documentation'
  },
  {
    icon: Settings,
    label: 'Configuration',
    view: ViewType.CONFIGURATION,
    description: 'Configure settings'
  },
];

export function Sidebar({ currentView, onViewChange, isOpen }: SidebarProps) {
  if (!isOpen) return null;

  return (
    <aside
      className="w-64 border-r bg-background p-4 overflow-y-auto"
      role="navigation"
      aria-label="Main navigation"
    >
      <nav className="space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.view;

          return (
            <button
              key={item.view}
              onClick={() => onViewChange(item.view)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-accent hover:text-accent-foreground'
              )}
              aria-current={isActive ? 'page' : undefined}
              title={item.description}
            >
              <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
