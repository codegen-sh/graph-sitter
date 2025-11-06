'use client';

import { useState } from 'react';
import { Save, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { ProgrammingLanguage, GroupBy } from '@/types';

export function ConfigurationPanel() {
  const [config, setConfig] = useState({
    repositoryName: 'graph-sitter',
    baseDir: '/home/user/graph-sitter',
    language: ProgrammingLanguage.PYTHON,
    subdirectories: ['src', 'tests'],
    defaultGroupBy: GroupBy.FILE,
    maxPrs: 5,
    theme: 'auto',
    editorFontSize: 14,
    editorTabSize: 2,
  });

  const handleSave = () => {
    // In production, this would save to the API
    toast.success('Configuration saved successfully');
  };

  const handleReset = () => {
    toast.success('Configuration reset to defaults');
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Repository Configuration</CardTitle>
          <CardDescription>
            Configure repository settings and behavior
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Repository Name</label>
              <Input
                value={config.repositoryName}
                onChange={(e) =>
                  setConfig({ ...config, repositoryName: e.target.value })
                }
                aria-label="Repository name"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Base Directory</label>
              <Input
                value={config.baseDir}
                onChange={(e) => setConfig({ ...config, baseDir: e.target.value })}
                aria-label="Base directory"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Language</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={config.language}
                onChange={(e) =>
                  setConfig({ ...config, language: e.target.value as ProgrammingLanguage })
                }
                aria-label="Programming language"
              >
                {Object.values(ProgrammingLanguage).map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Default Grouping</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={config.defaultGroupBy}
                onChange={(e) =>
                  setConfig({ ...config, defaultGroupBy: e.target.value as GroupBy })
                }
                aria-label="Default grouping strategy"
              >
                {Object.values(GroupBy).map((group) => (
                  <option key={group} value={group}>
                    {group}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">
              Subdirectories
              <Badge variant="secondary" className="ml-2">
                {config.subdirectories.length} selected
              </Badge>
            </label>
            <div className="flex flex-wrap gap-2">
              {config.subdirectories.map((dir) => (
                <Badge key={dir} variant="outline">
                  {dir}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
        <CardFooter className="flex gap-2">
          <Button onClick={handleSave} className="gap-2">
            <Save className="h-4 w-4" />
            Save Configuration
          </Button>
          <Button onClick={handleReset} variant="outline" className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Reset to Defaults
          </Button>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Editor Preferences</CardTitle>
          <CardDescription>Customize editor settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Font Size</label>
              <Input
                type="number"
                min="10"
                max="24"
                value={config.editorFontSize}
                onChange={(e) =>
                  setConfig({ ...config, editorFontSize: parseInt(e.target.value) })
                }
                aria-label="Editor font size"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Tab Size</label>
              <Input
                type="number"
                min="2"
                max="8"
                value={config.editorTabSize}
                onChange={(e) =>
                  setConfig({ ...config, editorTabSize: parseInt(e.target.value) })
                }
                aria-label="Editor tab size"
              />
            </div>
          </div>
        </CardContent>
        <CardFooter>
          <Button onClick={handleSave} className="gap-2">
            <Save className="h-4 w-4" />
            Save Preferences
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
