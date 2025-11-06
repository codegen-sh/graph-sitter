'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Play, Eye, GitBranch, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { apiClient } from '@/lib/api-client';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { CodemodRunResult, ExecutionStatus, GroupBy } from '@/types';
import { DiffDisplay } from './diff-display';
import { ProgressIndicator } from './progress-indicator';

interface CodemodExecutorProps {
  codemodLabel: string;
}

export function CodemodExecutor({ codemodLabel }: CodemodExecutorProps) {
  const [result, setResult] = useState<CodemodRunResult | null>(null);
  const [executionStatus, setExecutionStatus] = useState<ExecutionStatus>(ExecutionStatus.PENDING);
  const [branchName, setBranchName] = useState('');
  const [commitMessage, setCommitMessage] = useState('');
  const [showDiff, setShowDiff] = useState(false);

  const previewMutation = useMutation({
    mutationFn: async () => {
      setExecutionStatus(ExecutionStatus.RUNNING);
      const response = await apiClient.getDiff({
        codemod: {
          user_code: `# ${codemodLabel} codemod`,
          label: codemodLabel,
        },
        max_transactions: 1000,
        max_seconds: 300,
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data) {
        setResult(data);
        setExecutionStatus(data.is_complete ? ExecutionStatus.SUCCESS : ExecutionStatus.PARTIAL);
        setShowDiff(true);
        toast.success('Preview generated successfully');
      }
    },
    onError: (error: any) => {
      setExecutionStatus(ExecutionStatus.FAILED);
      toast.error(error.message || 'Failed to generate preview');
    },
  });

  const executeMutation = useMutation({
    mutationFn: async () => {
      setExecutionStatus(ExecutionStatus.RUNNING);
      const response = await apiClient.runCodemod(
        `# ${codemodLabel} codemod`,
        true
      );
      return response.data;
    },
    onSuccess: (data) => {
      if (data) {
        setResult(data);
        setExecutionStatus(data.is_complete ? ExecutionStatus.SUCCESS : ExecutionStatus.PARTIAL);
        toast.success('Codemod executed and committed successfully');
      }
    },
    onError: (error: any) => {
      setExecutionStatus(ExecutionStatus.FAILED);
      toast.error(error.message || 'Failed to execute codemod');
    },
  });

  const createBranchMutation = useMutation({
    mutationFn: async () => {
      if (!branchName || !commitMessage) {
        throw new Error('Branch name and commit message are required');
      }

      setExecutionStatus(ExecutionStatus.RUNNING);
      const response = await apiClient.createBranch({
        codemod: {
          user_code: `# ${codemodLabel} codemod`,
          label: codemodLabel,
        },
        commit_msg: commitMessage,
        branch_config: {
          branch_name: branchName,
        },
        grouping_config: {
          group_by: GroupBy.FILE,
          max_prs: 5,
        },
      });
      return response.data;
    },
    onSuccess: (data) => {
      if (data) {
        setExecutionStatus(ExecutionStatus.SUCCESS);
        toast.success(`Created ${data.branches.length} branch(es) successfully`);
      }
    },
    onError: (error: any) => {
      setExecutionStatus(ExecutionStatus.FAILED);
      toast.error(error.message || 'Failed to create branch');
    },
  });

  const getStatusBadge = () => {
    switch (executionStatus) {
      case ExecutionStatus.SUCCESS:
        return (
          <Badge variant="success" className="gap-1">
            <CheckCircle2 className="h-3 w-3" />
            Success
          </Badge>
        );
      case ExecutionStatus.FAILED:
        return (
          <Badge variant="destructive" className="gap-1">
            <AlertCircle className="h-3 w-3" />
            Failed
          </Badge>
        );
      case ExecutionStatus.RUNNING:
        return (
          <Badge variant="warning" className="gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            Running
          </Badge>
        );
      case ExecutionStatus.PARTIAL:
        return (
          <Badge variant="warning" className="gap-1">
            <AlertCircle className="h-3 w-3" />
            Partial
          </Badge>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>{codemodLabel}</CardTitle>
              <CardDescription>
                Execute codemod and preview changes
              </CardDescription>
            </div>
            {getStatusBadge()}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {executionStatus === ExecutionStatus.RUNNING && (
            <ProgressIndicator message="Executing codemod..." />
          )}

          {result && (
            <div className="space-y-3">
              <div className="p-3 rounded-md bg-muted">
                <h4 className="font-medium mb-1">Observation</h4>
                <p className="text-sm text-muted-foreground">{result.observation}</p>
              </div>

              {result.files_changed !== undefined && (
                <div className="flex items-center gap-4 text-sm">
                  <span>
                    <strong>Files Changed:</strong> {result.files_changed}
                  </span>
                  {result.execution_time && (
                    <span>
                      <strong>Execution Time:</strong> {result.execution_time}ms
                    </span>
                  )}
                </div>
              )}

              {result.error && (
                <div className="error-state">
                  <h4 className="font-medium mb-1">Error</h4>
                  <p className="text-sm">{result.error.message}</p>
                  {result.error.stack_trace && (
                    <pre className="mt-2 text-xs overflow-x-auto">
                      {result.error.stack_trace}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="space-y-2">
            <h4 className="font-medium text-sm">Branch Configuration</h4>
            <Input
              placeholder="Branch name (e.g., feature/codemod-changes)"
              value={branchName}
              onChange={(e) => setBranchName(e.target.value)}
              aria-label="Branch name"
            />
            <Input
              placeholder="Commit message"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              aria-label="Commit message"
            />
          </div>
        </CardContent>
        <CardFooter className="flex gap-2">
          <Button
            onClick={() => previewMutation.mutate()}
            disabled={previewMutation.isPending || executionStatus === ExecutionStatus.RUNNING}
            variant="outline"
            className="gap-2"
          >
            <Eye className="h-4 w-4" />
            Preview Changes
          </Button>

          <Button
            onClick={() => executeMutation.mutate()}
            disabled={executeMutation.isPending || executionStatus === ExecutionStatus.RUNNING}
            className="gap-2"
          >
            <Play className="h-4 w-4" />
            Execute & Commit
          </Button>

          <Button
            onClick={() => createBranchMutation.mutate()}
            disabled={
              createBranchMutation.isPending ||
              executionStatus === ExecutionStatus.RUNNING ||
              !branchName ||
              !commitMessage
            }
            variant="secondary"
            className="gap-2"
          >
            <GitBranch className="h-4 w-4" />
            Create Branch & PR
          </Button>
        </CardFooter>
      </Card>

      {showDiff && result?.highlighted_diff && (
        <Card>
          <CardHeader>
            <CardTitle>Code Changes</CardTitle>
            <CardDescription>
              Review the changes that will be applied
            </CardDescription>
          </CardHeader>
          <CardContent>
            <DiffDisplay diff={result.highlighted_diff} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
