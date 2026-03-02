# TypeScript Migration Guide

**Status**: In Progress  
**Started**: March 2, 2026  
**Current Phase**: Component Migration  

---

## Progress Update: March 2, 2026

### ✅ Recently Completed
- Converted `Success.jsx` → `Success.tsx`
- Converted `TaskStatus.jsx` → `TaskStatus.tsx`
- Updated Vite config with path aliases
- Created comprehensive type definitions

### 📋 Migration Progress

**Components**: 2/6 converted (33%)
**Tests**: 0/3 converted (0%)

---

## Overview

This document tracks the migration of the Client Portal from JavaScript to TypeScript. The migration follows a gradual approach to minimize disruption while gaining type safety benefits incrementally.

---

## Current State

### ✅ Completed
- TypeScript configuration (`tsconfig.json`)
- Type definitions foundation (`src/types/index.ts`)
- Vite configuration with path aliases
- TypeScript dependencies installed:
  - `typescript@^5.3.0`
  - `@types/react@^19.2.7`
  - `@types/react-dom@^19.2.3`

### 🔄 In Progress
- Component migration (0/9 files converted)
- Test file migration (0/3 files converted)

### 📋 Remaining Files
- [x] ~~`src/main.jsx`~~
- [x] ~~`src/App.jsx`~~
- [ ] `src/components/TaskSubmissionForm.jsx`
- [ ] `src/components/AnalyticsDashboard.jsx`
- [x] ~~`src/components/TaskStatus.jsx`~~ ✅ Converted
- [x] ~~`src/components/Success.jsx`~~ ✅ Converted
- [ ] `src/components/__tests__/Success.test.jsx`
- [ ] `src/components/__tests__/TaskStatus.test.jsx`
- [ ] `src/components/__tests__/TaskSubmissionForm.test.jsx`

---

## Migration Approach

### Phase 1: Foundation (✅ Complete)
1. Add TypeScript configuration
2. Install type definitions
3. Create base types
4. Configure path aliases

### Phase 2: Utility Files (Next)
1. Convert utility functions first
2. Add types for API responses
3. Create custom hook types

### Phase 3: Components (Bottom-Up)
1. Start with simple presentational components
2. Move to complex stateful components
3. Convert App.jsx last

### Phase 4: Tests
1. Convert test files alongside components
2. Add type-safe testing utilities

---

## Migration Checklist

### Configuration
- [x] `tsconfig.json` created
- [x] TypeScript dependencies installed
- [x] Path aliases configured in vite.config
- [ ] ESLint configured for TypeScript
- [ ] `allowJs` set to `true` during migration

### Type Definitions
- [x] Core types (`Task`, `TaskStatus`, etc.)
- [ ] API response types
- [ ] Component prop types
- [ ] Event handler types
- [ ] Custom hook types

### Components
- [ ] `main.jsx` → `main.tsx`
- [ ] `App.jsx` → `App.tsx`
- [ ] `TaskSubmissionForm.jsx` → `TaskSubmissionForm.tsx`
- [ ] `AnalyticsDashboard.jsx` → `AnalyticsDashboard.tsx`
- [x] `TaskStatus.jsx` → `TaskStatus.tsx` ✅
- [x] `Success.jsx` → `Success.tsx` ✅

### Tests
- [ ] `Success.test.jsx` → `Success.test.tsx`
- [ ] `TaskStatus.test.jsx` → `TaskStatus.test.tsx`
- [ ] `TaskSubmissionForm.test.jsx` → `TaskSubmissionForm.test.tsx`

---

## Migration Steps for Each File

### 1. Rename File
```bash
mv Component.jsx Component.tsx
```

### 2. Add Imports
```typescript
import React, { FC, useState, ChangeEvent, FormEvent } from 'react';
import { Task, TaskFormData, TaskDomain } from '@/types';
```

### 3. Add Type Annotations
```typescript
// Props
interface ComponentProps {
  onSubmit: (data: TaskFormData) => void;
  isLoading?: boolean;
}

// Component with typed props
const Component: FC<ComponentProps> = ({ onSubmit, isLoading = false }) => {
  // State
  const [formData, setFormData] = useState<TaskFormData>({
    title: '',
    description: '',
    domain: 'general',
  });

  // Event handlers
  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onSubmit(formData);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  return (/* JSX */);
};
```

### 4. Update Tests
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { Component } from './Component';

describe('Component', () => {
  it('renders correctly', () => {
    render(<Component onSubmit={jest.fn()} />);
    expect(screen.getByRole('form')).toBeInTheDocument();
  });
});
```

---

## Type Definitions Reference

### Core Types (Already Defined)
```typescript
// src/types/index.ts
export type TaskStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type TaskDomain = 'general' | 'legal' | 'accounting' | ...;

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  domain: TaskDomain;
  result?: string;
  error?: string;
  progress?: number;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}
```

### Common Patterns

#### Component Props
```typescript
interface Props {
  // Required props
  onSubmit: (data: FormData) => void;
  taskId: string;

  // Optional props with defaults
  className?: string;
  isLoading?: boolean;

  // Event handlers
  onClick?: () => void;
  onChange?: (value: string) => void;

  // Children
  children?: React.ReactNode;
}
```

#### State Types
```typescript
// Simple state
const [count, setCount] = useState<number>(0);

// Complex state
const [tasks, setTasks] = useState<Task[]>([]);

// Reducer
type Action =
  | { type: 'ADD_TASK'; payload: Task }
  | { type: 'REMOVE_TASK'; payload: string }
  | { type: 'UPDATE_TASK'; payload: Partial<Task> };

const [state, dispatch] = useReducer<TaskReducer, TaskState>(
  reducer,
  initialState
);
```

#### Event Handlers
```typescript
// Form events
const handleSubmit = (e: FormEvent<HTMLFormElement>) => { ... }
const handleChange = (e: ChangeEvent<HTMLInputElement>) => { ... }

// Mouse events
const handleClick = (e: MouseEvent<HTMLButtonElement>) => { ... }

// Keyboard events
const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => { ... }
```

---

## ESLint Configuration

Update `eslint.config.js` for TypeScript:

```javascript
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      '@typescript-eslint/no-unused-vars': 'warn',
      '@typescript-eslint/explicit-function-return-type': 'off',
    },
  },
)
```

---

## Testing Strategy

### Type-Safe Testing
```typescript
import { renderHook, act } from '@testing-library/react'
import { useTask } from './useTask'

describe('useTask', () => {
  it('should load task data', async () => {
    const { result } = renderHook(() => useTask('task-123'))

    await act(async () => {
      await result.current.loadTask()
    })

    expect(result.current.task).toEqual({
      id: 'task-123',
      title: 'Test Task',
      status: 'completed',
    })
  })
})
```

### Mock Types
```typescript
// __mocks__/api.ts
import { Task, ApiResponse } from '@/types'

export const mockTask: Task = {
  id: 'test-1',
  title: 'Test Task',
  description: 'Test Description',
  status: 'completed',
  domain: 'general',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
}

export const mockApiResponse: ApiResponse<Task> = {
  success: true,
  data: mockTask,
}
```

---

## Common Issues and Solutions

### Issue: "Cannot find module" Error
**Solution**: Ensure path aliases are configured in both `tsconfig.json` and `vite.config.ts`

### Issue: React Types Not Found
**Solution**: Install `@types/react` and `@types/react-dom`

### Issue: JSX Type Error
**Solution**: Add `"jsx": "react-jsx"` to `tsconfig.json`

### Issue: Import Errors in Tests
**Solution**: Add type definitions for testing libraries:
```bash
npm install -D @types/jest @testing-library/jest-dom
```

---

## Progress Tracking

### Week 1: Foundation ✅
- [x] TypeScript configuration
- [x] Base types defined
- [x] Path aliases configured

### Week 2: Simple Components
- [ ] Convert `Success.jsx` (simplest component)
- [ ] Convert `TaskStatus.jsx`
- [ ] Update corresponding tests

### Week 3: Complex Components
- [ ] Convert `TaskSubmissionForm.jsx`
- [ ] Convert `AnalyticsDashboard.jsx`
- [ ] Add comprehensive type definitions

### Week 4: App Entry Points
- [ ] Convert `App.jsx`
- [ ] Convert `main.jsx`
- [ ] Final type checking
- [ ] Remove `allowJs` flag

---

## Benefits Achieved So Far

1. **Centralized Type Definitions**: Single source of truth for data models
2. **IDE Support**: Better autocomplete and IntelliSense
3. **Self-Documentation**: Types serve as living documentation
4. **Early Error Detection**: Catch errors at compile time

---

## Next Steps

1. **Configure ESLint for TypeScript**
   - Add `typescript-eslint` plugin
   - Update rules for TypeScript

2. **Start Component Migration**
   - Begin with `Success.jsx` (simplest)
   - Follow migration checklist

3. **Add More Type Definitions**
   - API client types
   - Custom hook types
   - Event types

4. **Update CI/CD**
   - Add TypeScript type checking
   - Update build pipeline

---

## Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [React TypeScript Cheat Sheet](https://react-typescript-cheatsheet.netlify.app/)
- [TypeScript with Vite](https://vitejs.dev/guide/)
- [Testing Library TypeScript](https://testing-library.com/docs/react-testing-library/intro/)

---

**Last Updated**: March 2, 2026  
**Next Review**: March 9, 2026  
**Migration Lead**: Development Team
