'use client';

import { ServerInfo, WarmupState } from '@/types';
import { Badge } from './ui/badge';

interface StatusBarProps {
  sandboxInfo?: ServerInfo;
  daemonInfo?: ServerInfo;
}

export function StatusBar({ sandboxInfo, daemonInfo }: StatusBarProps) {
  const getWarmupBadgeVariant = (state?: WarmupState) => {
    switch (state) {
      case WarmupState.COMPLETE:
        return 'success';
      case WarmupState.IN_PROGRESS:
        return 'warning';
      case WarmupState.FAILED:
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  return (
    <footer
      className="border-t bg-muted/50 px-4 py-2 text-sm"
      role="contentinfo"
      aria-label="Status information"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Sandbox:</span>
            {sandboxInfo ? (
              <>
                <span className="status-dot status-dot-success" aria-label="Connected" />
                <Badge variant={getWarmupBadgeVariant(sandboxInfo.warmup_state)}>
                  {sandboxInfo.warmup_state || 'Unknown'}
                </Badge>
              </>
            ) : (
              <>
                <span className="status-dot status-dot-error" aria-label="Disconnected" />
                <span className="text-destructive">Disconnected</span>
              </>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Daemon:</span>
            {daemonInfo ? (
              <>
                <span className="status-dot status-dot-success" aria-label="Connected" />
                <Badge variant="success">Connected</Badge>
              </>
            ) : (
              <>
                <span className="status-dot status-dot-error" aria-label="Disconnected" />
                <span className="text-destructive">Disconnected</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 text-muted-foreground">
          {sandboxInfo?.repo_name && (
            <span>Repository: {sandboxInfo.repo_name}</span>
          )}
          {sandboxInfo?.synced_commit && (
            <span>Commit: {sandboxInfo.synced_commit.substring(0, 7)}</span>
          )}
        </div>
      </div>
    </footer>
  );
}
