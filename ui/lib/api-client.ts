import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  ServerInfo,
  GetDiffRequest,
  CreateBranchRequest,
  CodemodRunResult,
  CreateBranchResponse,
  CodemodMetadata,
  SearchFilters,
  SearchResult,
  RepositoryConfig,
  GitInfo,
  FileInfo,
  SymbolInfo,
  ExecutionHistoryItem,
  ApiResponse,
} from '@/types';

class ApiClient {
  private sandboxClient: AxiosInstance;
  private daemonClient: AxiosInstance;

  constructor() {
    this.sandboxClient = axios.create({
      baseURL: process.env.NEXT_PUBLIC_SANDBOX_URL || 'http://localhost:4000',
      timeout: 300000, // 5 minutes for long-running operations
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.daemonClient = axios.create({
      baseURL: process.env.NEXT_PUBLIC_DAEMON_URL || 'http://localhost:8000',
      timeout: 300000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add response interceptor for error handling
    [this.sandboxClient, this.daemonClient].forEach(client => {
      client.interceptors.response.use(
        response => response,
        this.handleError
      );
    });
  }

  private handleError = (error: AxiosError): Promise<ApiResponse<null>> => {
    console.error('API Error:', error);

    const response: ApiResponse<null> = {
      status: error.response?.status || 500,
      error: error.message,
      message: error.response?.data?.message || 'An unexpected error occurred',
    };

    return Promise.reject(response);
  };

  // Sandbox Server Endpoints

  /**
   * Get server health and info
   */
  async getSandboxInfo(): Promise<ApiResponse<ServerInfo>> {
    try {
      const response = await this.sandboxClient.get<ServerInfo>('/');
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Execute codemod and get diff without committing
   */
  async getDiff(request: GetDiffRequest): Promise<ApiResponse<CodemodRunResult>> {
    try {
      const response = await this.sandboxClient.post<CodemodRunResult>('/diff', request);
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Create branches and PRs with grouped flags
   */
  async createBranch(request: CreateBranchRequest): Promise<ApiResponse<CreateBranchResponse>> {
    try {
      const response = await this.sandboxClient.post<CreateBranchResponse>('/branch', request);
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  // Daemon Server Endpoints

  /**
   * Get daemon server info
   */
  async getDaemonInfo(): Promise<ApiResponse<ServerInfo>> {
    try {
      const response = await this.daemonClient.get<ServerInfo>('/');
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Run codemod on local repository
   */
  async runCodemod(
    codemodCode: string,
    commit: boolean = false
  ): Promise<ApiResponse<CodemodRunResult>> {
    try {
      const response = await this.daemonClient.post<CodemodRunResult>('/run', {
        codemod_code: codemodCode,
        commit,
      });
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  // Codemod Management

  /**
   * List all available codemods
   */
  async listCodemods(filters?: SearchFilters): Promise<ApiResponse<SearchResult>> {
    try {
      const response = await this.daemonClient.get<SearchResult>('/codemods', {
        params: filters,
      });
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Get codemod details by label
   */
  async getCodemod(label: string): Promise<ApiResponse<CodemodMetadata>> {
    try {
      const response = await this.daemonClient.get<CodemodMetadata>(`/codemods/${label}`);
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Create new codemod
   */
  async createCodemod(codemod: Partial<CodemodMetadata>): Promise<ApiResponse<CodemodMetadata>> {
    try {
      const response = await this.daemonClient.post<CodemodMetadata>('/codemods', codemod);
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Update existing codemod
   */
  async updateCodemod(
    label: string,
    updates: Partial<CodemodMetadata>
  ): Promise<ApiResponse<CodemodMetadata>> {
    try {
      const response = await this.daemonClient.put<CodemodMetadata>(
        `/codemods/${label}`,
        updates
      );
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Delete codemod
   */
  async deleteCodemod(label: string): Promise<ApiResponse<void>> {
    try {
      const response = await this.daemonClient.delete(`/codemods/${label}`);
      return {
        status: response.status,
        message: 'Codemod deleted successfully',
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  // Repository Operations

  /**
   * Get repository configuration
   */
  async getRepositoryConfig(): Promise<ApiResponse<RepositoryConfig>> {
    try {
      const response = await this.daemonClient.get<RepositoryConfig>('/repository/config');
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Update repository configuration
   */
  async updateRepositoryConfig(
    config: Partial<RepositoryConfig>
  ): Promise<ApiResponse<RepositoryConfig>> {
    try {
      const response = await this.daemonClient.put<RepositoryConfig>(
        '/repository/config',
        config
      );
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Get git information
   */
  async getGitInfo(): Promise<ApiResponse<GitInfo>> {
    try {
      const response = await this.daemonClient.get<GitInfo>('/repository/git');
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * List repository files
   */
  async listFiles(directory?: string): Promise<ApiResponse<FileInfo[]>> {
    try {
      const response = await this.daemonClient.get<FileInfo[]>('/repository/files', {
        params: { directory },
      });
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Get file content
   */
  async getFileContent(filePath: string): Promise<ApiResponse<FileInfo>> {
    try {
      const response = await this.daemonClient.get<FileInfo>(`/repository/files/${filePath}`);
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Search symbols in codebase
   */
  async searchSymbols(query: string): Promise<ApiResponse<SymbolInfo[]>> {
    try {
      const response = await this.daemonClient.get<SymbolInfo[]>('/repository/symbols', {
        params: { query },
      });
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  // Execution History

  /**
   * Get execution history
   */
  async getExecutionHistory(limit: number = 50): Promise<ApiResponse<ExecutionHistoryItem[]>> {
    try {
      const response = await this.daemonClient.get<ExecutionHistoryItem[]>('/history', {
        params: { limit },
      });
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  /**
   * Get execution details
   */
  async getExecutionDetails(executionId: string): Promise<ApiResponse<ExecutionHistoryItem>> {
    try {
      const response = await this.daemonClient.get<ExecutionHistoryItem>(
        `/history/${executionId}`
      );
      return {
        data: response.data,
        status: response.status,
      };
    } catch (error) {
      return error as ApiResponse<null>;
    }
  }

  // Utility Methods

  /**
   * Check if servers are healthy
   */
  async healthCheck(): Promise<{ sandbox: boolean; daemon: boolean }> {
    const [sandboxHealth, daemonHealth] = await Promise.allSettled([
      this.getSandboxInfo(),
      this.getDaemonInfo(),
    ]);

    return {
      sandbox: sandboxHealth.status === 'fulfilled' && sandboxHealth.value.status === 200,
      daemon: daemonHealth.status === 'fulfilled' && daemonHealth.value.status === 200,
    };
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
