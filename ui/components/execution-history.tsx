'use client';

import { useState } from 'react';
import { Clock, CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { formatDate, formatDuration } from '@/lib/utils';
import { ExecutionStatus } from '@/types';

export function ExecutionHistory() {
  // Mock execution history data
  const history = [
    {
      id: '1',
      codemod_label: 'python2_to_python3',
      timestamp: new Date().toISOString(),
      status: ExecutionStatus.SUCCESS,
      duration: 5420,
      files_changed: 12,
      branch: 'feature/python3-migration',
    },
    {
      id: '2',
      codemod_label: 'unittest_to_pytest',
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      status: ExecutionStatus.SUCCESS,
      duration: 3210,
      files_changed: 8,
    },
    {
      id: '3',
      codemod_label: 'add_type_annotations',
      timestamp: new Date(Date.now() - 7200000).toISOString(),
      status: ExecutionStatus.FAILED,
      duration: 1250,
      files_changed: 0,
      error: 'Failed to parse file: src/complex.py',
    },
    {
      id: '4',
      codemod_label: 'delete_dead_code',
      timestamp: new Date(Date.now() - 86400000).toISOString(),
      status: ExecutionStatus.SUCCESS,
      duration: 8930,
      files_changed: 24,
    },
  ];

  const getStatusIcon = (status: ExecutionStatus) => {
    switch (status) {
      case ExecutionStatus.SUCCESS:
        return <CheckCircle2 className="h-5 w-5 text-success" />;
      case ExecutionStatus.FAILED:
        return <XCircle className="h-5 w-5 text-destructive" />;
      case ExecutionStatus.RUNNING:
        return <Clock className="h-5 w-5 text-warning animate-pulse" />;
      default:
        return <AlertCircle className="h-5 w-5 text-muted-foreground" />;
    }
  };

  const getStatusBadge = (status: ExecutionStatus) => {
    switch (status) {
      case ExecutionStatus.SUCCESS:
        return <Badge variant="success">Success</Badge>;
      case ExecutionStatus.FAILED:
        return <Badge variant="destructive">Failed</Badge>;
      case ExecutionStatus.RUNNING:
        return <Badge variant="warning">Running</Badge>;
      default:
        return <Badge variant="secondary">Pending</Badge>;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Execution History</CardTitle>
        <CardDescription>
          View past codemod executions and their results
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {history.map((item) => (
            <div
              key={item.id}
              className="border rounded-md p-4 hover:bg-accent/50 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1">
                  {getStatusIcon(item.status)}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium truncate">{item.codemod_label}</h4>
                      {getStatusBadge(item.status)}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span>{formatDate(item.timestamp)}</span>
                      <span>Duration: {formatDuration(item.duration)}</span>
                      <span>Files: {item.files_changed}</span>
                    </div>
                    {item.branch && (
                      <div className="mt-1">
                        <Badge variant="outline" className="text-xs">
                          Branch: {item.branch}
                        </Badge>
                      </div>
                    )}
                    {item.error && (
                      <div className="mt-2 text-sm text-destructive">
                        Error: {item.error}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {history.length === 0 && (
            <div className="empty-state py-12">
              <Clock className="empty-state-icon" />
              <p>No execution history yet</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
