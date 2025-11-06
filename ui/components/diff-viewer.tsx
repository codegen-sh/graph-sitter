'use client';

import { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { FileText, Download } from 'lucide-react';
import { downloadFile } from '@/lib/utils';

export function DiffViewer() {
  const [splitView, setSplitView] = useState(true);

  // Mock diff data
  const mockDiff = `diff --git a/src/example.py b/src/example.py
index 1234567..abcdefg 100644
--- a/src/example.py
+++ b/src/example.py
@@ -1,10 +1,12 @@
 import os
-import sys
+from typing import List, Optional

 def process_data(data):
-    """Process data"""
-    result = []
-    for item in data:
-        result.append(item * 2)
-    return result
+    """Process data with type hints"""
+    result: List[int] = []
+    for item in data:
+        result.append(item * 2)
+    return result`;

  const handleDownload = () => {
    downloadFile(mockDiff, 'changes.diff', 'text/plain');
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Diff Viewer</CardTitle>
            <CardDescription>
              Review code changes before and after transformation
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant={splitView ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSplitView(true)}
            >
              Split View
            </Button>
            <Button
              variant={!splitView ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSplitView(false)}
            >
              Unified View
            </Button>
            <Button variant="outline" size="sm" onClick={handleDownload}>
              <Download className="h-4 w-4 mr-2" />
              Download
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <Badge variant="success">+8 additions</Badge>
            <Badge variant="destructive">-5 deletions</Badge>
            <Badge variant="secondary">1 file changed</Badge>
          </div>

          <div className="border rounded-md overflow-hidden">
            <div className="bg-muted px-3 py-2 flex items-center gap-2 border-b">
              <FileText className="h-4 w-4" />
              <span className="font-mono text-sm">src/example.py</span>
            </div>
            <pre className="p-4 overflow-x-auto text-sm font-mono bg-background">
              <code>{mockDiff}</code>
            </pre>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
