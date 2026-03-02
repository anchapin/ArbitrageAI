# ArbitrageAI Client Portal

**Version**: 0.1.0
**Framework**: React 19 + Vite
**Status**: Production Ready

---

## Overview

The ArbitrageAI Client Portal is a modern, responsive web application that allows clients to:

- ✅ Submit tasks for automated execution
- ✅ Monitor task progress in real-time
- ✅ View analytics and performance metrics
- ✅ Manage account settings and billing

### Key Features

| Feature | Description | Status |
|---------|-------------|--------|
| **Task Submission** | Submit tasks with file attachments | ✅ Complete |
| **Real-time Status** | Live task status updates | ✅ Complete |
| **Analytics Dashboard** | Performance metrics and insights | ✅ Complete |
| **Responsive Design** | Mobile and desktop support | ✅ Complete |
| **Type Safety** | TypeScript migration ready | 🔄 In Progress |

---

## Quick Start

### Prerequisites

- **Node.js**: v18+ or v20+ (LTS recommended)
- **npm**: v9+ or **pnpm**: v8+ or **yarn**: v1.22+
- **Backend API**: ArbitrageAI backend running (see [Backend Setup](../../README.md))

### Installation

```bash
# Navigate to client portal directory
cd src/client_portal

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Edit .env and configure API URL
# VITE_API_URL=http://localhost:8000/api
```

### Development

```bash
# Start development server (with hot reload)
npm run dev

# Open browser to http://localhost:5173
```

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

---

## Project Structure

```
src/client_portal/
├── public/                 # Static assets
│   └── vite.svg
├── src/
│   ├── components/         # React components
│   │   ├── __tests__/      # Component tests
│   │   ├── AnalyticsDashboard.jsx
│   │   ├── TaskStatus.jsx
│   │   ├── TaskSubmissionForm.jsx
│   │   └── Success.jsx
│   ├── types/              # TypeScript types (migration)
│   │   └── index.ts
│   ├── assets/             # Images, fonts, etc.
│   │   └── react.svg
│   ├── App.jsx             # Main application component
│   ├── App.css             # Application styles
│   ├── main.jsx            # Entry point
│   └── index.css           # Global styles
├── .env.example            # Environment variables template
├── eslint.config.js        # ESLint configuration
├── index.html              # HTML entry point
├── package.json            # Dependencies and scripts
├── vite.config.js          # Vite configuration
├── vitest.config.js        # Vitest testing configuration
└── README.md               # This file
```

---

## Available Scripts

### Development

```bash
# Start dev server with hot reload
npm run dev

# Start dev server on custom port
npm run dev -- --port 3000
```

### Building

```bash
# Build for production
npm run build

# Build with analysis (bundle size)
npm run build -- --mode analyze
```

### Testing

```bash
# Run tests in watch mode
npm run test

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Run tests once (CI mode)
npm run test -- --run
```

### Linting

```bash
# Lint all files
npm run lint

# Lint and fix automatically
npm run lint -- --fix
```

### Preview

```bash
# Preview production build
npm run preview
```

---

## Component Documentation

### TaskSubmissionForm

**Location**: `src/components/TaskSubmissionForm.jsx`

**Purpose**: Allows users to submit new tasks with optional file attachments.

**Props**:
```javascript
{
  onSubmit: (taskData) => void,  // Callback when form is submitted
  className?: string              // Optional CSS class
}
```

**Usage**:
```javascript
import TaskSubmissionForm from './TaskSubmissionForm';

function App() {
  const handleSubmit = async (taskData) => {
    const response = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(taskData)
    });
    // Handle response...
  };

  return <TaskSubmissionForm onSubmit={handleSubmit} />;
}
```

---

### TaskStatus

**Location**: `src/components/TaskStatus.jsx`

**Purpose**: Displays real-time task status and progress.

**Props**:
```javascript
{
  task: {
    id: string,
    title: string,
    status: 'pending' | 'processing' | 'completed' | 'failed',
    progress?: number,
    result?: string,
    error?: string
  },
  onRefresh?: () => void,      // Optional refresh callback
  showActions?: boolean        // Show action buttons
}
```

**Usage**:
```javascript
import TaskStatus from './TaskStatus';

function TaskList({ tasks }) {
  return (
    <div>
      {tasks.map(task => (
        <TaskStatus 
          key={task.id} 
          task={task}
          onRefresh={() => refreshTask(task.id)}
          showActions={true}
        />
      ))}
    </div>
  );
}
```

---

### AnalyticsDashboard

**Location**: `src/components/AnalyticsDashboard.jsx`

**Purpose**: Displays task analytics and performance metrics.

**Props**:
```javascript
{
  analytics: {
    totalTasks: number,
    completedTasks: number,
    failedTasks: number,
    successRate: number,
    averageCompletionTime: number,
    tasksByDomain: object,
    tasksByStatus: object
  },
  timeRange?: 'day' | 'week' | 'month' | 'year'
}
```

**Usage**:
```javascript
import AnalyticsDashboard from './AnalyticsDashboard';

function Dashboard() {
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    fetchAnalytics().then(setAnalytics);
  }, []);

  return <AnalyticsDashboard analytics={analytics} timeRange="week" />;
}
```

---

### Success

**Location**: `src/components/Success.jsx`

**Purpose**: Displays success messages after task completion.

**Props**:
```javascript
{
  message: string,            // Success message
  taskResult?: string,        // Optional task result
  onContinue?: () => void     // Callback to continue
}
```

**Usage**:
```javascript
import Success from './Success';

function TaskComplete({ result }) {
  return (
    <Success 
      message="Task completed successfully!"
      taskResult={result}
      onContinue={() => navigateToDashboard()}
    />
  );
}
```

---

## API Integration

### Environment Variables

Create a `.env` file in the root directory:

```bash
# API Configuration
VITE_API_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/api/ws

# Feature Flags
VITE_ENABLE_ANALYTICS=true
VITE_ENABLE_FILE_UPLOAD=true

# Optional: Authentication
VITE_AUTH_ENABLED=false
```

### API Client

The application communicates with the ArbitrageAI backend API. Example API calls:

```javascript
// Submit a new task
const submitTask = async (taskData) => {
  const response = await fetch(`${import.meta.env.VITE_API_URL}/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(taskData),
  });
  
  if (!response.ok) {
    throw new Error('Failed to submit task');
  }
  
  return response.json();
};

// Get task status
const getTaskStatus = async (taskId) => {
  const response = await fetch(`${import.meta.env.VITE_API_URL}/tasks/${taskId}`);
  return response.json();
};

// Get analytics
const getAnalytics = async (timeRange = 'week') => {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL}/analytics?range=${timeRange}`
  );
  return response.json();
};
```

### WebSocket Integration

For real-time updates:

```javascript
// Connect to WebSocket
const ws = new WebSocket(import.meta.env.VITE_WS_URL);

ws.onopen = () => {
  console.log('Connected to WebSocket');
  ws.send(JSON.stringify({ type: 'subscribe', channel: 'tasks' }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'task_update') {
    updateTaskStatus(message.task);
  }
};
```

---

## Testing

### Running Tests

```bash
# Run all tests
npm run test

# Run specific test file
npm run test -- TaskStatus.test.jsx

# Run tests matching pattern
npm run test -- --grep "submission"
```

### Writing Tests

Tests use React Testing Library and Vitest:

```javascript
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import TaskSubmissionForm from './TaskSubmissionForm';

describe('TaskSubmissionForm', () => {
  it('submits form with valid data', async () => {
    const onSubmit = vi.fn();
    render(<TaskSubmissionForm onSubmit={onSubmit} />);
    
    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: 'Test Task' }
    });
    
    fireEvent.click(screen.getByText('Submit'));
    
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Test Task'
      })
    );
  });
});
```

### Test Coverage

```bash
# Generate coverage report
npm run test:coverage

# Open coverage report in browser
open coverage/index.html
```

**Coverage Goal**: >80%

---

## Styling

### CSS Architecture

The application uses plain CSS with BEM-like naming conventions:

```css
/* Component container */
.task-status {
  /* ... */
}

/* Element */
.task-status__title {
  /* ... */
}

/* Modifier */
.task-status--completed {
  /* ... */
}
```

### Responsive Design

Mobile-first approach with breakpoints:

```css
/* Mobile (default) */
.component {
  padding: 1rem;
}

/* Tablet */
@media (min-width: 768px) {
  .component {
    padding: 2rem;
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .component {
    padding: 3rem;
  }
}
```

---

## Deployment

### Build for Production

```bash
# Install dependencies
npm install

# Build
npm run build

# Output: dist/ directory
```

### Deploy to Static Hosting

The `dist/` directory can be deployed to:

- **Vercel**: Automatic deployment from Git
- **Netlify**: Drag & drop or Git integration
- **AWS S3 + CloudFront**: Manual upload
- **Docker**: Use provided Dockerfile

### Docker Deployment

```bash
# Build Docker image
docker build -t arbitrageai-client .

# Run container
docker run -p 80:80 arbitrageai-client
```

### Environment-Specific Builds

```bash
# Staging
VITE_API_URL=https://staging-api.arbitrageai.com npm run build

# Production
VITE_API_URL=https://api.arbitrageai.com npm run build
```

---

## Troubleshooting

### Common Issues

#### 1. API Connection Errors

**Symptom**: "Failed to fetch" errors in console

**Solution**:
- Verify `VITE_API_URL` in `.env` is correct
- Ensure backend is running
- Check CORS configuration on backend

#### 2. Build Failures

**Symptom**: `npm run build` fails

**Solution**:
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
npm run build
```

#### 3. Hot Reload Not Working

**Symptom**: Changes don't reflect in browser

**Solution**:
- Restart dev server: `Ctrl+C` then `npm run dev`
- Clear browser cache
- Check Vite config for exclude patterns

#### 4. Test Failures

**Symptom**: Tests fail unexpectedly

**Solution**:
```bash
# Clear Vitest cache
npx vitest --clearCache

# Run tests in isolation
npm run test -- --isolate
```

### Debugging

```javascript
// Enable debug logging
localStorage.setItem('debug', 'arbitrageai:*');

// In browser console
debug = 'arbitrageai:*'
```

---

## Contributing

### Development Workflow

1. **Create Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow existing code style
   - Add tests for new features
   - Update documentation

3. **Run Checks**
   ```bash
   npm run lint
   npm run test
   npm run build
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Submit PR**
   - Push to GitHub
   - Create pull request
   - Request review

### Code Style

- **Components**: PascalCase (`TaskStatus.jsx`)
- **Utilities**: camelCase (`utils.js`)
- **CSS**: BEM-like (`.block__element--modifier`)
- **Imports**: Group by type (React, libraries, local)

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new task submission form
fix: resolve WebSocket reconnection issue
docs: update API integration examples
test: add tests for AnalyticsDashboard
refactor: simplify task status logic
```

---

## TypeScript Migration

**Status**: 🔄 In Progress

See [TYPESCRIPT_MIGRATION_EVALUATION.md](../../TYPESCRIPT_MIGRATION_EVALUATION.md) for detailed migration plan.

### Current Status

| File | Status | Priority |
|------|--------|----------|
| `types/index.ts` | ✅ Complete | High |
| `main.jsx` | ⏳ Pending | Low |
| `App.jsx` | ⏳ Pending | High |
| `Success.jsx` | ⏳ Pending | Low |
| `TaskStatus.jsx` | ⏳ Pending | Medium |
| `TaskSubmissionForm.jsx` | ⏳ Pending | High |
| `AnalyticsDashboard.jsx` | ⏳ Pending | High |

### Migration Guide

1. **Install TypeScript**
   ```bash
   npm install --save-dev typescript @types/react @types/react-dom
   ```

2. **Rename File**
   ```bash
   mv Component.jsx Component.tsx
   ```

3. **Add Type Annotations**
   ```typescript
   interface Props {
     task: Task;
     onRefresh: () => void;
   }
   
   export default function Component({ task, onRefresh }: Props) {
     // ...
   }
   ```

4. **Fix Type Errors**
   ```bash
   npx tsc --noEmit
   ```

5. **Test**
   ```bash
   npm run test
   ```

---

## Performance Optimization

### Bundle Size

```bash
# Analyze bundle
npm install --save-dev rollup-plugin-visualizer

# Add to vite.config.js
import { visualizer } from "rollup-plugin-visualizer";

export default {
  plugins: [visualizer()],
};
```

### Code Splitting

```javascript
// Lazy load components
const AnalyticsDashboard = React.lazy(() => 
  import('./AnalyticsDashboard')
);

// Use with Suspense
<Suspense fallback={<Loading />}>
  <AnalyticsDashboard />
</Suspense>
```

### Memoization

```javascript
// Memoize expensive calculations
const processedData = useMemo(() => 
  processData(analytics), 
  [analytics]
);

// Memoize callbacks
const handleSubmit = useCallback((data) => {
  onSubmit(data);
}, [onSubmit]);
```

---

## Security

### Best Practices

1. **Input Validation**: Validate all user inputs
2. **XSS Prevention**: Use React's built-in escaping
3. **CSRF Protection**: Include CSRF tokens in requests
4. **Secure Headers**: Configure security headers
5. **Environment Variables**: Never commit secrets

### Content Security Policy

```html
<!-- Add to index.html -->
<meta 
  http-equiv="Content-Security-Policy" 
  content="default-src 'self'; script-src 'self' 'unsafe-inline';"
>
```

---

## Browser Support

| Browser | Version | Support |
|---------|---------|---------|
| Chrome | 90+ | ✅ Full |
| Firefox | 88+ | ✅ Full |
| Safari | 14+ | ✅ Full |
| Edge | 90+ | ✅ Full |
| Opera | 76+ | ✅ Full |

---

## Resources

### Documentation

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [React Router](https://reactrouter.com/)
- [Testing Library](https://testing-library.com/)

### Tools

- [TypeScript Playground](https://www.typescriptlang.org/play)
- [Vite Config Validator](https://vite-config-validator.vercel.app/)
- [Bundle Phobia](https://bundlephobia.com/) - Check package sizes

### Community

- [React Discord](https://discord.gg/react)
- [Vite Discord](https://chat.vite.dev/)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/reactjs)

---

## License

MIT License - See [LICENSE](../../LICENSE) for details.

---

## Support

**Issues**: [GitHub Issues](https://github.com/anchapin/ArbitrageAI/issues)
**Email**: support@arbitrageai.com
**Documentation**: [Full Documentation](../../docs/)

---

**Last Updated**: March 2, 2026
**Maintained By**: ArbitrageAI Development Team
