'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { CodemodList } from '@/components/codemod-list';
import { CodemodExecutor } from '@/components/codemod-executor';
import { DiffViewer } from '@/components/diff-viewer';
import { Sidebar } from '@/components/sidebar';
import { Header } from '@/components/header';
import { StatusBar } from '@/components/status-bar';
import { RepositoryBrowser } from '@/components/repository-browser';
import { ConfigurationPanel } from '@/components/configuration-panel';
import { DocumentationPanel } from '@/components/documentation-panel';
import { ExecutionHistory } from '@/components/execution-history';
import { ViewType } from '@/types';

export default function HomePage() {
  const [currentView, setCurrentView] = useState<ViewType>(ViewType.CODEMODS);
  const [selectedCodemodLabel, setSelectedCodemodLabel] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Fetch server info
  const { data: sandboxInfo } = useQuery({
    queryKey: ['sandbox-info'],
    queryFn: async () => {
      const response = await apiClient.getSandboxInfo();
      return response.data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  const { data: daemonInfo } = useQuery({
    queryKey: ['daemon-info'],
    queryFn: async () => {
      const response = await apiClient.getDaemonInfo();
      return response.data;
    },
    refetchInterval: 30000,
  });

  const renderView = () => {
    switch (currentView) {
      case ViewType.CODEMODS:
        return (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1">
              <CodemodList
                onSelectCodemod={setSelectedCodemodLabel}
                selectedLabel={selectedCodemodLabel}
              />
            </div>
            <div className="lg:col-span-2">
              {selectedCodemodLabel ? (
                <CodemodExecutor codemodLabel={selectedCodemodLabel} />
              ) : (
                <div className="empty-state h-full">
                  <div className="empty-state-icon">📝</div>
                  <h3 className="text-lg font-semibold mb-2">No Codemod Selected</h3>
                  <p>Select a codemod from the list to view details and execute</p>
                </div>
              )}
            </div>
          </div>
        );

      case ViewType.DIFF:
        return <DiffViewer />;

      case ViewType.REPOSITORY:
        return <RepositoryBrowser />;

      case ViewType.CONFIGURATION:
        return <ConfigurationPanel />;

      case ViewType.DOCUMENTATION:
        return <DocumentationPanel />;

      case ViewType.HISTORY:
        return <ExecutionHistory />;

      default:
        return <div>View not implemented</div>;
    }
  };

  return (
    <div className="flex h-screen flex-col">
      <Header
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        sidebarOpen={sidebarOpen}
      />

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          currentView={currentView}
          onViewChange={setCurrentView}
          isOpen={sidebarOpen}
        />

        <main
          id="main-content"
          className="flex-1 overflow-y-auto p-6 bg-background"
          role="main"
        >
          {renderView()}
        </main>
      </div>

      <StatusBar sandboxInfo={sandboxInfo} daemonInfo={daemonInfo} />
    </div>
  );
}
