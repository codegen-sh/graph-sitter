# Graph-Sitter UI

A comprehensive, accessible web interface for the Graph-Sitter codemod management system. This application provides an intuitive way to browse, execute, and manage code transformations across your codebase.

## Features

### Core Functionality

- **Codemod Management**
  - Browse and search 48+ available codemods
  - Filter by category, language, and tags
  - View detailed documentation for each codemod
  - Execute codemods with real-time feedback

- **Code Transformation**
  - Preview changes before applying
  - Side-by-side diff viewer
  - Syntax-highlighted code display
  - Support for Python and TypeScript/JavaScript

- **Execution Controls**
  - Execute and commit changes
  - Create branches and pull requests
  - Configure grouping strategies
  - Progress tracking for long-running operations

- **Repository Browser**
  - Navigate repository file structure
  - Preview file contents
  - Search files by name

- **Version Control Integration**
  - View affected files and changes
  - Create branches with custom configurations
  - Track execution history
  - Monitor git status and commits

### UI/UX Features

- **Responsive Design**
  - Mobile-first approach
  - Adaptive layouts for all screen sizes
  - Touch-friendly interactions

- **Accessibility (WCAG 2.1 AA Compliant)**
  - Keyboard navigation support
  - Screen reader compatibility
  - High contrast mode support
  - Focus indicators on all interactive elements
  - Skip to main content link
  - ARIA labels and landmarks

- **Theme Support**
  - Light and dark modes
  - System preference detection
  - Persistent theme selection

- **User Experience**
  - Toast notifications for feedback
  - Loading states and progress indicators
  - Error handling with user-friendly messages
  - Empty states with helpful guidance

## Technology Stack

- **Framework**: Next.js 14 (React 18)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)
- **Code Display**: Prism + React Syntax Highlighter
- **Diff Viewing**: React Diff Viewer
- **Testing**: Jest + React Testing Library
- **HTTP Client**: Axios

## Getting Started

### Prerequisites

- Node.js 18.x or higher
- npm or yarn or pnpm
- Running Graph-Sitter sandbox server (port 4000)
- Running Graph-Sitter daemon server (port 8000)

### Installation

1. Navigate to the UI directory:
```bash
cd /path/to/graph-sitter/ui
```

2. Install dependencies:
```bash
npm install
# or
yarn install
# or
pnpm install
```

3. Create a `.env.local` file:
```env
NEXT_PUBLIC_API_URL=http://localhost:3000
NEXT_PUBLIC_SANDBOX_URL=http://localhost:4000
NEXT_PUBLIC_DAEMON_URL=http://localhost:8000
```

### Development

Start the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:3000`.

### Building for Production

Build the application:
```bash
npm run build
```

Start the production server:
```bash
npm start
```

### Testing

Run tests:
```bash
npm test
```

Run tests in watch mode:
```bash
npm run test:watch
```

Generate coverage report:
```bash
npm run test:coverage
```

### Type Checking

Run TypeScript type checking:
```bash
npm run type-check
```

## Project Structure

```
ui/
├── app/                      # Next.js app directory
│   ├── layout.tsx           # Root layout
│   ├── page.tsx             # Home page
│   └── providers.tsx        # Context providers
├── components/              # React components
│   ├── ui/                  # Base UI components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   └── badge.tsx
│   ├── codemod-list.tsx     # Codemod listing
│   ├── codemod-executor.tsx # Execution controls
│   ├── diff-viewer.tsx      # Diff display
│   ├── repository-browser.tsx
│   ├── configuration-panel.tsx
│   ├── documentation-panel.tsx
│   └── execution-history.tsx
├── lib/                     # Utilities and helpers
│   ├── api-client.ts        # API client
│   └── utils.ts             # Utility functions
├── types/                   # TypeScript type definitions
│   └── index.ts
├── styles/                  # Global styles
│   └── globals.css
├── __tests__/              # Test files
│   ├── components/
│   └── lib/
├── public/                 # Static assets
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── next.config.js
└── README.md
```

## API Integration

The UI communicates with two backend services:

### Sandbox Server (Port 4000)
- `GET /` - Health check and server info
- `POST /diff` - Generate diff without committing
- `POST /branch` - Create branches and PRs

### Daemon Server (Port 8000)
- `GET /` - Health check
- `POST /run` - Execute codemod on local repository
- `GET /codemods` - List available codemods
- `GET /codemods/:label` - Get codemod details
- `GET /repository/config` - Get repository configuration
- `GET /repository/git` - Get git information
- `GET /history` - Get execution history

## Component Documentation

### CodemodList
Displays a searchable, filterable list of available codemods.

**Props:**
- `onSelectCodemod: (label: string) => void` - Callback when codemod is selected
- `selectedLabel: string | null` - Currently selected codemod

**Features:**
- Real-time search
- Category filtering
- Tag display
- Responsive grid layout

### CodemodExecutor
Provides controls for executing codemods with various options.

**Props:**
- `codemodLabel: string` - Label of codemod to execute

**Features:**
- Preview changes before committing
- Execute and commit
- Create branches and PRs
- Progress tracking
- Error handling

### DiffViewer
Displays code changes in split or unified view.

**Features:**
- Split view (side-by-side)
- Unified view (inline)
- Syntax highlighting
- Download diff
- Line numbers
- Addition/deletion highlighting

### RepositoryBrowser
Browse repository files and preview contents.

**Features:**
- Tree view navigation
- File search
- Content preview
- Syntax highlighting
- File metadata

## Accessibility

This application follows WCAG 2.1 Level AA guidelines:

### Keyboard Navigation
- All interactive elements are keyboard accessible
- Logical tab order throughout the application
- Visible focus indicators
- Escape key closes modals and overlays

### Screen Readers
- Semantic HTML elements
- ARIA labels for all interactive elements
- ARIA live regions for dynamic content
- Descriptive alt text for images
- Screen reader-only text for context

### Visual
- Minimum 4.5:1 contrast ratio for text
- Minimum 3:1 contrast ratio for UI components
- Focus indicators are clearly visible
- Text can be resized up to 200%
- No information conveyed by color alone

### Motion
- Respects `prefers-reduced-motion` setting
- Optional animation controls
- No automatic motion without user control

### Testing Accessibility
```bash
npm install @axe-core/react
```

The application includes axe-core for automated accessibility testing in development mode.

## Performance Optimization

- Code splitting with Next.js dynamic imports
- Image optimization with Next.js Image component
- React Query for efficient data fetching and caching
- Debounced search inputs
- Virtualized lists for large datasets
- Lazy loading of components

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Frontend API URL | `http://localhost:3000` |
| `NEXT_PUBLIC_SANDBOX_URL` | Sandbox server URL | `http://localhost:4000` |
| `NEXT_PUBLIC_DAEMON_URL` | Daemon server URL | `http://localhost:8000` |

## Contributing

### Code Style
- Follow existing code patterns
- Use TypeScript for type safety
- Write tests for new components
- Follow accessibility guidelines
- Document complex logic

### Testing Requirements
- Unit tests for utility functions
- Component tests for UI components
- Integration tests for key user flows
- Accessibility tests with axe
- Minimum 70% code coverage

## Troubleshooting

### Common Issues

**Problem:** Application won't connect to backend
- Ensure sandbox and daemon servers are running
- Check environment variables in `.env.local`
- Verify CORS settings on backend

**Problem:** Styles not loading correctly
- Clear Next.js cache: `rm -rf .next`
- Rebuild: `npm run build`

**Problem:** TypeScript errors
- Run type checking: `npm run type-check`
- Update dependencies: `npm update`

**Problem:** Tests failing
- Clear Jest cache: `npm test -- --clearCache`
- Update snapshots: `npm test -- -u`

## License

See the main Graph-Sitter repository for license information.

## Support

For issues and questions:
- GitHub Issues: https://github.com/graphsitter/graphsitter/issues
- Documentation: https://docs.graphsitter.com
- Community: https://discord.gg/graphsitter

## Acknowledgments

- Built with Next.js and React
- UI components inspired by shadcn/ui
- Icons from Lucide React
- Syntax highlighting by Prism
