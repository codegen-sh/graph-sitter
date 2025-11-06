'use client';

interface DiffDisplayProps {
  diff: string;
}

export function DiffDisplay({ diff }: DiffDisplayProps) {
  const lines = diff.split('\n');

  return (
    <div className="border rounded-md overflow-hidden bg-background">
      <div className="overflow-x-auto">
        <table className="w-full font-mono text-sm">
          <tbody>
            {lines.map((line, index) => {
              let className = '';
              let prefix = '';

              if (line.startsWith('+')) {
                className = 'bg-green-500/10 text-green-700 dark:text-green-300';
                prefix = '+';
              } else if (line.startsWith('-')) {
                className = 'bg-red-500/10 text-red-700 dark:text-red-300';
                prefix = '-';
              } else if (line.startsWith('@@')) {
                className = 'bg-blue-500/10 text-blue-700 dark:text-blue-300 font-semibold';
              }

              return (
                <tr key={index} className={className}>
                  <td className="px-2 py-0.5 text-muted-foreground text-right select-none w-12">
                    {index + 1}
                  </td>
                  <td className="px-2 py-0.5 whitespace-pre-wrap break-all">
                    {line}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
