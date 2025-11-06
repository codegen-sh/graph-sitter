'use client';

interface ProgressIndicatorProps {
  progress?: number; // 0-100
  message?: string;
  steps?: {
    total: number;
    current: number;
  };
}

export function ProgressIndicator({ progress, message, steps }: ProgressIndicatorProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{message || 'Processing...'}</span>
        {steps && (
          <span className="text-muted-foreground">
            Step {steps.current} of {steps.total}
          </span>
        )}
        {progress !== undefined && (
          <span className="font-medium">{Math.round(progress)}%</span>
        )}
      </div>

      {progress !== undefined ? (
        <div className="progress-bar">
          <div
            className="progress-bar-fill"
            style={{ width: `${progress}%` }}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      ) : (
        <div className="progress-bar">
          <div
            className="progress-bar-fill animate-pulse-slow"
            style={{ width: '60%' }}
            role="progressbar"
            aria-label="Loading"
          />
        </div>
      )}
    </div>
  );
}
