# Claude Code Skills - Documentação Completa

> 25 skills configuradas para auto-ativação inteligente
> Última Atualização: 2024-11-14

## Índice

1. [Visão Geral](#visão-geral)
2. [Guardrails (Crítico)](#guardrails-crítico)
   - [database-verification](#database-verification)
3. [Desenvolvimento Backend](#desenvolvimento-backend)
   - [backend-dev-guidelines](#backend-dev-guidelines)
4. [Desenvolvimento Frontend](#desenvolvimento-frontend)
   - [frontend-dev-guidelines](#frontend-dev-guidelines)
   - [frontend-design-excellence](#frontend-design-excellence)
5. [Testes e Qualidade](#testes-e-qualidade)
   - [python-testing-patterns](#python-testing-patterns)
   - [debugging-strategies](#debugging-strategies)
   - [python-performance-optimization](#python-performance-optimization)
6. [API e Arquitetura](#api-e-arquitetura)
   - [api-design-principles](#api-design-principles)
   - [llm-evaluation](#llm-evaluation)
7. [DevOps e Infraestrutura](#devops-e-infraestrutura)
   - [github-actions-templates](#github-actions-templates)
   - [prometheus-configuration](#prometheus-configuration)
   - [grafana-dashboards](#grafana-dashboards)
8. [Criação de Documentos](#criação-de-documentos)
   - [docx](#docx)
   - [pptx](#pptx)
   - [xlsx](#xlsx)
   - [pdf](#pdf)
9. [Utilitários](#utilitários)
   - [mcp-builder](#mcp-builder)
   - [skill-creator](#skill-creator)
10. [Workflows Avançados](#workflows-avançados)
    - [feature-dev-workflow](#feature-dev-workflow)
    - [code-review-parallel](#code-review-parallel)
    - [pr-review-agents](#pr-review-agents)
11. [Integração com Claude-Mem](#integração-com-claude-mem)
    - [claude-mem-integration](#claude-mem-integration)
12. [Outras Skills](#outras-skills)
    - [algorithmic-art](#algorithmic-art)
    - [artifacts-builder](#artifacts-builder)
    - [brand-guidelines](#brand-guidelines)
    - [canvas-design](#canvas-design)
    - [internal-comms](#internal-comms)
    - [product-self-knowledge](#product-self-knowledge)
    - [slack-gif-creator](#slack-gif-creator)
    - [theme-factory](#theme-factory)

---

## Visão Geral

Este diretório contém todas as skills globalmente disponíveis para o Claude Code.

**Estatísticas:**
- **Total de Skills**: 25
- **Com File Triggers**: 18 (auto-ativam ao editar arquivos)
- **Prioridade Crítica**: 1
- **Alta Prioridade**: 5
- **Total de Documentação**: 1,500+ linhas

---

# Guardrails (Crítico)

---

## database-verification

# Database Verification Guardrail

## Purpose

This is a **CRITICAL GUARDRAIL** skill that prevents dangerous database operations and common errors.

**Enforcement Level**: BLOCK (this skill can prevent edits)

## When This Skill Activates

- Editing schema.prisma files
- Creating or modifying migrations (Prisma, Alembic, raw SQL)
- Keywords: database, prisma, SQL, migration, schema, table, column, alter, drop
- Any database schema changes

## Critical Checks

### 1. Column Name Verification

**Problem**: Typos in column names cause runtime errors that are hard to debug.

```prisma
// ❌ DANGER: Typo will cause runtime errors
model User {
  id        String   @id @default(uuid())
  emial     String   @unique  // ❌ TYPO: "emial" instead of "email"
  createdAt DateTime @default(now())
}

// ✅ SAFE: Correct column name
model User {
  id        String   @id @default(uuid())
  email     String   @unique  // ✅ Correct
  createdAt DateTime @default(now())
}
```

**BEFORE SAVING** any schema change:
1. Read the entire schema file
2. Check all column names for common typos:
   - `emial` → should be `email`
   - `pasword` → should be `password`
   - `usrname` → should be `username`
   - `cratedAt` → should be `createdAt`
   - `updtedAt` → should be `updatedAt`
3. If typo detected, **BLOCK** the change and alert

### 2. Dangerous Operations

```prisma
// ❌ DANGER: Dropping column without backup
model User {
  id    String @id
  // email String  // ❌ Commented out = will be dropped!
}

// ⚠️ WARNING: Adding non-nullable column to existing table
model User {
  id       String @id
  email    String
  newField String  // ❌ Existing rows will fail if no default!
}

// ✅ SAFE: Adding non-nullable with default
model User {
  id       String @id
  email    String
  newField String @default("")  // ✅ Has default value
}
```

**Required Checks Before Migration**:

- [ ] Dropping columns? → Warn about data loss
- [ ] Adding non-nullable column? → Requires @default or make nullable
- [ ] Changing column type? → Check if data is compatible
- [ ] Removing @unique or @id? → Will break existing queries
- [ ] Renaming column? → Use migration, not delete+add

### 3. Migration Safety

```sql
-- ❌ DANGER: Dropping table without confirmation
DROP TABLE users;

-- ❌ DANGER: Altering column type (data loss risk)
ALTER TABLE users ALTER COLUMN age TYPE INTEGER;  -- Was VARCHAR

-- ✅ SAFE: Using transactions
BEGIN;
  ALTER TABLE users ADD COLUMN new_field VARCHAR;
COMMIT;
```

## Pre-Migration Checklist

Before running `prisma migrate dev` or `alembic upgrade head`:

- [ ] All column names spelled correctly (no typos)
- [ ] New non-nullable columns have @default or are optional
- [ ] No accidental column deletions (commented out fields)
- [ ] Foreign key relationships are correct
- [ ] Indexes are on the right columns
- [ ] Enum values are spelled correctly
- [ ] No breaking changes without migration plan

## Safe Migration Workflow

### Prisma
```bash
# 1. Check current schema
npx prisma validate

# 2. Create migration (DON'T run yet)
npx prisma migrate dev --create-only

# 3. Review generated SQL
cat prisma/migrations/[timestamp]_[name]/migration.sql

# 4. If safe, apply
npx prisma migrate dev

# 5. Generate client
npx prisma generate
```

### Alembic (Python)
```bash
# 1. Create migration
alembic revision --autogenerate -m "description"

# 2. Review generated migration
cat alembic/versions/[hash]_description.py

# 3. If safe, apply
alembic upgrade head
```

## Common Mistakes to Catch

### Mistake 1: Typo in Relation
```prisma
// ❌ TYPO: "auther" instead of "author"
model Post {
  id       String @id
  auther   User   @relation(fields: [authorId], references: [id])
}
```

### Mistake 2: Missing Cascade Delete
```prisma
// ⚠️ WARNING: No cascade = orphaned records
model Post {
  id     String @id
  author User   @relation(fields: [authorId], references: [id])
  // ❌ Missing: onDelete: Cascade
}

// ✅ BETTER
model Post {
  id     String @id
  author User   @relation(fields: [authorId], references: [id], onDelete: Cascade)
}
```

### Mistake 3: Enum Value Typo
```prisma
// ❌ TYPO: "Pendng" instead of "Pending"
enum OrderStatus {
  Pending  // ✅
  Shipped  // ✅
  Pendng   // ❌ TYPO
}
```

## Blocking Criteria

This skill **BLOCKS** changes if:

1. ❌ Column name contains common typo
2. ❌ Dropping column without explicit confirmation
3. ❌ Adding non-nullable column without default to existing table
4. ❌ Changing column type without data migration plan
5. ❌ Enum value contains typo
6. ❌ Relation field name doesn't match relation name

## Warning Criteria

This skill **WARNS** about:

1. ⚠️ Missing cascade delete on foreign keys
2. ⚠️ Missing indexes on frequently queried columns
3. ⚠️ Very long column names (>50 chars)
4. ⚠️ Missing updated_at timestamp on main tables
5. ⚠️ No unique constraint on email fields

## Quick Reference

| Operation | Risk Level | Required Check |
|-----------|-----------|----------------|
| Add column | Low | Check nullable/default |
| Drop column | HIGH | Confirm + backup |
| Rename column | Medium | Use migration |
| Change type | HIGH | Data compatibility |
| Add relation | Low | Verify field names |
| Drop relation | Medium | Check cascade |
| Add enum value | Low | Spell check |
| Remove enum value | HIGH | Check usage |

---

**REMEMBER**: This skill is a guardrail. When it blocks you, it's protecting your database from runtime errors that are painful to debug!

---

# Desenvolvimento Backend

---

## backend-dev-guidelines

# Backend Development Guidelines

## Purpose

This skill provides comprehensive patterns and best practices for backend development following the **Controller-Service-Repository** architecture pattern.

Supports both:
- **Node.js/TypeScript** with Express/NestJS
- **Python** with FastAPI

## When This Skill Activates

- Editing backend source files (backend/**/*.ts, app/**/*.py, services/**/*.py)
- Keywords: backend, controller, service, repository, API, endpoint, route
- Creating or modifying API endpoints
- Implementing business logic

## Architecture Pattern

### Layer Responsibilities

```
HTTP Request
    ↓
📍 ROUTE (defines URL + HTTP method)
    ↓
🎯 CONTROLLER (handles HTTP concerns)
    ↓
💼 SERVICE (contains business logic)
    ↓
💾 REPOSITORY (data access layer)
    ↓
Database
```

**Golden Rule**: Each layer has ONE job. Never skip layers or mix responsibilities.

## 1. Node.js/TypeScript Patterns

### Controller Pattern

```typescript
// ✅ GOOD: Clean controller
import { Request, Response } from 'express';
import { UserService } from '../services/user.service';

class UserController extends BaseController {
  constructor(private userService: UserService) {
    super();
  }

  async getUser(req: Request, res: Response) {
    try {
      const userId = req.params.id;

      // Validate input
      if (!userId) {
        return res.status(400).json({ error: 'User ID required' });
      }

      // Delegate to service
      const user = await this.userService.findById(userId);

      // Format response
      return res.json({
        success: true,
        data: user
      });

    } catch (error) {
      return this.handleError(error, res);
    }
  }
}

// ❌ BAD: Controller with business logic
class UserController {
  async getUser(req: Request, res: Response) {
    // ❌ Direct database access
    const user = await prisma.user.findUnique({ where: { id: req.params.id } });

    // ❌ Business logic in controller
    if (user.status === 'banned') {
      throw new Error('User is banned');
    }

    return res.json(user);
  }
}
```

### Service Pattern

```typescript
// ✅ GOOD: Service with business logic
class UserService {
  constructor(private userRepo: UserRepository) {}

  async findById(id: string): Promise<User> {
    const user = await this.userRepo.findById(id);

    if (!user) {
      throw new NotFoundError('User not found');
    }

    // Business rule: Don't return banned users
    if (user.status === 'banned') {
      throw new ForbiddenError('User is banned');
    }

    // Transform data according to business rules
    return this.sanitizeUser(user);
  }

  private sanitizeUser(user: User): User {
    const { password, secretToken, ...safe } = user;
    return safe;
  }
}
```

### Repository Pattern

```typescript
// ✅ GOOD: Repository for data access only
class UserRepository {
  constructor(private prisma: PrismaClient) {}

  async findById(id: string): Promise<User | null> {
    return this.prisma.user.findUnique({
      where: { id },
      include: {
        profile: true,
        roles: true
      }
    });
  }

  async create(data: CreateUserData): Promise<User> {
    return this.prisma.user.create({
      data,
      include: { profile: true }
    });
  }
}
```

## 2. Python/FastAPI Patterns

### Router Pattern (FastAPI Controller)

```python
# ✅ GOOD: Clean router
from fastapi import APIRouter, Depends, HTTPException
from app.services.user_service import UserService
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    user_service: UserService = Depends()
):
    """Get user by ID - delegates to service"""
    return await user_service.find_by_id(user_id)

# ❌ BAD: Business logic in router
@router.get("/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    # ❌ Direct database access
    user = db.query(User).filter(User.id == user_id).first()

    # ❌ Business logic here
    if not user:
        raise HTTPException(404, "User not found")
    if user.status == "banned":
        raise HTTPException(403, "User is banned")

    return user
```

### Service Pattern (Python)

```python
# ✅ GOOD: Service with business logic
from app.repositories.user_repository import UserRepository
from app.exceptions import NotFoundError, ForbiddenError

class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def find_by_id(self, user_id: str) -> User:
        user = await self.user_repo.get_by_id(user_id)

        if not user:
            raise NotFoundError("User not found")

        # Business rule
        if user.status == "banned":
            raise ForbiddenError("User is banned")

        return self._sanitize(user)

    def _sanitize(self, user: User) -> User:
        # Remove sensitive fields
        user.password = None
        user.secret_token = None
        return user
```

### Repository Pattern (Python)

```python
# ✅ GOOD: Repository for data access
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_data: dict) -> User:
        user = User(**user_data)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
```

### Dependency Injection (FastAPI)

```python
# dependencies.py
from fastapi import Depends
from app.database import get_db
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService

async def get_user_service(db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    return UserService(user_repo)

# Usage in router
@router.get("/{user_id}")
async def get_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.find_by_id(user_id)
```

## Quick Reference

| Layer | Responsibility | Can Access | Cannot Access |
|-------|----------------|------------|---------------|
| Route | URL mapping | Controller | Service, Repository |
| Controller/Router | HTTP handling | Service | Repository, Database |
| Service | Business logic | Repository | HTTP (req/res), Database directly |
| Repository | Data access | Database | Business logic, HTTP |

## Checklist

Before implementing:
- [ ] Plan which layer handles what
- [ ] Controllers only handle HTTP
- [ ] Services contain ALL business logic
- [ ] Repositories only talk to database
- [ ] Error handling in all layers
- [ ] Proper dependency injection

**Remember**: When in doubt, ask yourself: "Which layer is responsible for this concern?"

---

# Desenvolvimento Frontend

---

## frontend-dev-guidelines

# Frontend Development Guidelines

## Purpose

This skill provides comprehensive patterns and best practices for modern React development using:
- React 19 with TypeScript
- TanStack Query (React Query) for data fetching
- TanStack Router for routing
- Modern hooks patterns

## When This Skill Activates

- Editing frontend files (*.tsx, *.jsx, components/, pages/)
- Keywords: react, component, hook, UI, page, form, state
- Creating or modifying components
- Implementing data fetching or routing

## Component Patterns

### Functional Components (Always Use These)

```typescript
// ✅ GOOD: Modern functional component with TypeScript
interface UserCardProps {
  user: User;
  onEdit?: (user: User) => void;
  className?: string;
}

export function UserCard({ user, onEdit, className }: UserCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className={cn('user-card', className)}>
      <h3>{user.name}</h3>
      <button onClick={() => setIsExpanded(!isExpanded)}>
        {isExpanded ? 'Show Less' : 'Show More'}
      </button>
      {isExpanded && (
        <div>
          <p>Email: {user.email}</p>
          {onEdit && (
            <button onClick={() => onEdit(user)}>Edit</button>
          )}
        </div>
      )}
    </div>
  );
}

// ❌ BAD: Class component (outdated)
class UserCard extends React.Component {
  // Don't use class components in new code
}
```

### Component Checklist

- [ ] Uses functional component (not class)
- [ ] Has TypeScript interface for props
- [ ] Props are destructured
- [ ] Optional props have `?` in interface
- [ ] Event handlers use descriptive names
- [ ] No complex logic (extract to hooks or utils)

## Data Fetching with TanStack Query

### Query Pattern

```typescript
// ✅ GOOD: Using useQuery
import { useQuery } from '@tanstack/react-query';

export function UserProfile({ userId }: { userId: string }) {
  const {
    data: user,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['user', userId],
    queryFn: () => api.users.getById(userId),
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 3,
  });

  if (isLoading) return <Skeleton />;
  if (error) return <ErrorMessage error={error} onRetry={refetch} />;

  return (
    <div>
      <h1>{user.name}</h1>
      <p>{user.email}</p>
    </div>
  );
}

// ❌ BAD: useState + useEffect for data fetching
export function UserProfile({ userId }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/users/${userId}`)
      .then(res => res.json())
      .then(setUser)
      .finally(() => setLoading(false));
  }, [userId]);

  // Don't do this - use useQuery!
}
```

### Mutation Pattern

```typescript
// ✅ GOOD: Using useMutation
import { useMutation, useQueryClient } from '@tanstack/react-query';

export function EditUserForm({ user }: { user: User }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: UpdateUserDTO) => api.users.update(user.id, data),
    onSuccess: (updatedUser) => {
      // Invalidate and refetch
      queryClient.invalidateQueries({ queryKey: ['user', user.id] });
      toast.success('User updated successfully');
    },
    onError: (error) => {
      toast.error('Failed to update user');
    }
  });

  const handleSubmit = (data: UpdateUserDTO) => {
    mutation.mutate(data);
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* form fields */}
      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending ? 'Saving...' : 'Save'}
      </button>
    </form>
  );
}
```

## Hooks Best Practices

### State Management

```typescript
// ✅ GOOD: Simple state
const [count, setCount] = useState(0);
const increment = () => setCount(prev => prev + 1);

// ✅ GOOD: Complex state with useReducer
type State = {
  items: Item[];
  filter: string;
  sortBy: 'name' | 'date';
};

type Action =
  | { type: 'SET_FILTER'; payload: string }
  | { type: 'SET_SORT'; payload: 'name' | 'date' };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_FILTER':
      return { ...state, filter: action.payload };
    case 'SET_SORT':
      return { ...state, sortBy: action.payload };
    default:
      return state;
  }
}

const [state, dispatch] = useReducer(reducer, initialState);
```

### useEffect Best Practices

```typescript
// ✅ GOOD: Effect with cleanup
useEffect(() => {
  const subscription = subscribeToUserPresence(userId);

  return () => {
    subscription.unsubscribe();
  };
}, [userId]);

// ❌ BAD: Missing dependencies
useEffect(() => {
  fetchUser(userId); // userId in effect...
}, []); // ...but not in dependencies!
```

## Common Pitfalls

### ❌ Don't Do This

```typescript
// 1. Mutating state directly
items.push(newItem); // ❌

// 2. Using index as key
{items.map((item, index) => (
  <div key={index}> // ❌
))}

// 3. Data fetching in useEffect
useEffect(() => {
  fetch('/api/data').then(setData);
}, []); // ❌ Use useQuery!
```

### ✅ Do This Instead

```typescript
// 1. Create new array
setItems([...items, newItem]); // ✅

// 2. Use unique ID as key
{items.map((item) => (
  <div key={item.id}> // ✅
))}

// 3. Use TanStack Query
const { data } = useQuery({...}); // ✅
```

## Quick Reference

| Pattern | Use Case | Example |
|---------|----------|---------|
| useState | Simple state | `const [count, setCount] = useState(0)` |
| useReducer | Complex state | State machine, multiple related values |
| useEffect | Side effects | Subscriptions, DOM updates |
| useCallback | Memoize functions | Callbacks to child components |
| useMemo | Memoize values | Expensive calculations |
| useQuery | Data fetching | GET requests, caching |
| useMutation | Data mutation | POST/PUT/DELETE requests |

## Component Checklist

- [ ] Functional component (not class)
- [ ] TypeScript props interface
- [ ] Loading and error states handled
- [ ] useEffect has proper dependencies
- [ ] Keys are unique and stable
- [ ] Accessibility attributes added

**Remember**: Modern React is all about hooks, functional components, and proper data fetching with TanStack Query!

---

## frontend-design-excellence

# Frontend Design Excellence

## Purpose
Generates distinctive, production-grade frontend interfaces with bold aesthetic choices, avoiding generic AI aesthetics and creating visually engaging experiences.

## When This Skill Activates

**Automatically activates on:**
- Keywords: "dashboard", "landing page", "UI design", "interface", "design system"
- File patterns: Frontend component files with design requirements
- Context: Frontend work requiring design decisions
- Intent: Creating visually distinctive, production-ready interfaces

**Manual activation:**
"Apply frontend-design-excellence to create this interface"

## Core Principles

### 1. Bold Aesthetic Choices
Make definitive design decisions rather than generic defaults:

❌ **Generic:**
- Gray backgrounds everywhere
- Default system fonts
- Minimal color (just black and white)
- Basic shadows
- Standard spacing

✅ **Distinctive:**
- Purposeful color palettes
- Thoughtful typography hierarchies
- Contextual visual treatments
- Memorable visual identity
- Intentional spacing systems

### 2. Distinctive Typography
Typography as a design element:

**Hierarchy:**
- Clear size relationships
- Weight variations
- Spacing and leading
- Contextual font choices

**Examples:**
```
Hero Title: 4rem, bold, tight leading (-0.02em)
Section Header: 2rem, semibold, balanced leading
Body: 1rem, regular, comfortable leading (1.6)
Caption: 0.875rem, medium, tight leading (1.4)
```

**Font Pairings:**
- Display + Sans-serif
- Serif + Monospace
- Custom brand fonts
- System font stacks done well

### 3. Purposeful Color Palettes
Context-aware color systems:

**Music Streaming App:**
- Vibrant gradients (purple to pink)
- High contrast for energy
- Dark mode optimized
- Accent colors for genres

**AI Security Startup:**
- Professional blues
- Trust-building greens
- Technical monospace elements
- High-tech gradients

**Financial Dashboard:**
- Confident blues
- Success greens, warning ambers
- Neutral grays for data
- Accent for key metrics

### 4. High-Impact Animations
Context-appropriate motion:

**Micro-interactions:**
- Button hover states
- Loading indicators
- State transitions
- Scroll reveals

**Page Transitions:**
- Smooth route changes
- Element entrances
- Contextual easing
- Performance-conscious

**Examples:**
```tsx
// Subtle hover lift
hover:translate-y-[-2px] transition-transform duration-200

// Smooth fade-in on mount
animate-in fade-in slide-in-from-bottom-4 duration-500

// Loading skeleton shimmer
animate-pulse bg-gradient-to-r from-gray-200 via-gray-100

// Stagger children animations
stagger-children-100ms
```

### 5. Visual Detail Attention
Thoughtful details that elevate:

**Shadows:**
- Layered elevation
- Contextual depth
- Colored shadows
- Inner shadows for depth

**Borders:**
- Gradient borders
- Contextual colors
- Thickness variations
- Rounded corners with purpose

**Backgrounds:**
- Gradient meshes
- Pattern overlays
- Texture layers
- Dynamic backgrounds

## Production-Ready Implementation

### Component Structure
```tsx
// ✅ Production-grade component
export function DashboardCard({
  title,
  value,
  trend,
  icon: Icon
}: DashboardCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="group relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-500/10 to-purple-500/10 p-6 backdrop-blur-sm border border-white/20 hover:border-white/40 transition-all duration-300 hover:shadow-2xl hover:shadow-blue-500/20"
    >
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-400 uppercase tracking-wider">
            {title}
          </p>
          <p className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
            {value}
          </p>
        </div>
        <div className="rounded-xl bg-blue-500/20 p-3 group-hover:scale-110 transition-transform duration-200">
          <Icon className="w-6 h-6 text-blue-400" />
        </div>
      </div>
      {trend && (
        <div className="mt-4 flex items-center gap-2">
          <TrendIcon className="w-4 h-4 text-green-400" />
          <span className="text-sm font-medium text-green-400">
            {trend}% increase
          </span>
        </div>
      )}
    </motion.div>
  );
}
```

### Design System Tokens
```ts
// Color palette
export const colors = {
  primary: {
    50: '#eff6ff',
    500: '#3b82f6',
    900: '#1e3a8a',
  },
  accent: {
    purple: '#a855f7',
    pink: '#ec4899',
  },
  semantic: {
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
  }
};

// Typography scale
export const typography = {
  hero: 'text-6xl font-bold tracking-tight',
  h1: 'text-4xl font-bold',
  h2: 'text-3xl font-semibold',
  body: 'text-base leading-relaxed',
  caption: 'text-sm text-gray-500',
};

// Spacing system
export const spacing = {
  section: 'py-24',
  container: 'px-6 lg:px-8',
  stack: 'space-y-8',
};
```

## Context-Aware Design

### Music Streaming Dashboard
**Aesthetic:**
- Vibrant, energetic colors
- Album art-driven design
- Fluid animations
- Glassmorphism effects

**Code example:**
```tsx
<div className="min-h-screen bg-gradient-to-br from-purple-900 via-pink-800 to-red-900">
  <div className="backdrop-blur-xl bg-black/30">
    {/* Content */}
  </div>
</div>
```

### AI Security Startup Landing
**Aesthetic:**
- Professional, technical
- Trust-building elements
- Data visualization
- Subtle tech motifs

**Code example:**
```tsx
<section className="relative overflow-hidden bg-slate-950">
  <div className="absolute inset-0 bg-gradient-to-b from-blue-500/10 to-transparent" />
  <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
  {/* Content */}
</section>
```

### Financial Dashboard
**Aesthetic:**
- Clean, data-focused
- High contrast for readability
- Confident colors
- Clear hierarchies

**Code example:**
```tsx
<div className="bg-white dark:bg-gray-900">
  <div className="grid grid-cols-4 gap-6">
    <MetricCard
      color="blue"
      trend="up"
      emphasis="high"
    />
  </div>
</div>
```

## Avoiding Common Pitfalls

### ❌ Generic AI Aesthetics
- Over-reliance on gradients everywhere
- Purple/blue default for everything
- Glassmorphism without purpose
- Rounded corners on everything
- Generic sans-serif only

### ✅ Intentional Design
- Gradients where they enhance meaning
- Colors chosen for context
- Glassmorphism for specific effects
- Border radius variation
- Typography that serves the content

## Animation Guidelines

### Performance-First
```tsx
// ✅ GPU-accelerated properties
transform: translate3d(0, 0, 0)
opacity: 0 → 1
scale: 0.95 → 1

// ❌ Avoid animating
width, height (use scale)
padding, margin (use transform)
color (use opacity on overlays)
```

### Easing Functions
```ts
// Natural motion
easeOut: cubic-bezier(0.16, 1, 0.3, 1) // Fast start, slow end
easeInOut: cubic-bezier(0.65, 0, 0.35, 1) // Balanced
spring: { type: "spring", stiffness: 300, damping: 30 }
```

### Timing
```ts
// Micro-interactions
instant: 100ms
quick: 200ms
normal: 300ms
slow: 500ms
dramatic: 700ms
```

## Accessibility + Beauty

Beauty doesn't sacrifice accessibility:

**Color Contrast:**
- WCAG AA minimum (4.5:1 for text)
- Test gradients for readability
- Provide high-contrast mode

**Focus States:**
- Visible focus indicators
- Keyboard navigation support
- Skip links for complex layouts

**Motion:**
- Respect prefers-reduced-motion
- Disable animations when requested
- Provide alternative indicators

**Example:**
```tsx
<motion.button
  whileHover={{ scale: 1.05 }}
  whileTap={{ scale: 0.95 }}
  className="focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
  // Respect motion preferences
  transition={{
    duration: 0.2,
    ...prefersReducedMotion && { duration: 0 }
  }}
>
  {children}
</motion.button>
```

## Integration with Frontend Guidelines

Works alongside **frontend-dev-guidelines**:
- Guidelines: React patterns, hooks, architecture
- Design Excellence: Visual design, aesthetics, UX polish

Combined approach:
1. Use frontend-dev-guidelines for component structure
2. Apply design-excellence for visual implementation
3. Result: Well-architected AND beautiful components

## Tools & Libraries

### Recommended Stack
- **Tailwind CSS**: Utility-first styling
- **Framer Motion**: Animation library
- **Radix UI**: Accessible primitives
- **Lucide Icons**: Icon library
- **Shadcn/ui**: Component patterns

### Color Tools
- **Coolors**: Palette generation
- **Realtime Colors**: Live preview
- **Color Contrast Checker**: Accessibility

### Typography
- **Fontjoy**: Font pairing
- **Type Scale**: Size relationships
- **Fluid Type Scale**: Responsive typography

## Examples by Use Case

### Dashboard
```tsx
- Dark mode optimized
- Data visualization emphasis
- Card-based layouts
- Real-time updates with smooth transitions
- Metric hierarchies with size and color
```

### Landing Page
```tsx
- Hero with gradient backgrounds
- Scroll-triggered animations
- Feature showcases
- Social proof sections
- Strong CTAs with hover effects
```

### Settings Panel
```tsx
- Clear section divisions
- Toggle switches with animations
- Form validation feedback
- Save state indicators
- Responsive layout
```

## Meta

**Type**: Domain
**Priority**: High
**Enforcement**: Suggest
**Author**: Anthropic (adapted from official plugin)
**Version**: 1.0.0

## Quick Checklist

Before shipping, verify:
- [ ] Bold design choices made (not defaults)
- [ ] Typography hierarchy clear
- [ ] Color palette contextual
- [ ] Animations smooth and purposeful
- [ ] Visual details polished
- [ ] Accessibility requirements met
- [ ] Performance optimized
- [ ] Responsive across devices
- [ ] Dark mode considered
- [ ] Loading states designed

---

# Testes e Qualidade

---

## python-testing-patterns

# Python Testing Patterns

## Purpose

This skill provides comprehensive patterns for testing Python applications using pytest, fixtures, mocking, and test-driven development (TDD) best practices.

## When This Skill Activates

- Editing test files (`test_*.py`, `*_test.py`, `tests/**/*.py`)
- Keywords: pytest, test, unittest, mock, fixture, coverage, TDD
- Creating or modifying test suites
- Writing unit, integration, or end-to-end tests

## Pytest Fundamentals

### Test Structure

```python
# ✅ GOOD: Clear test structure
import pytest
from app.services.user_service import UserService
from app.exceptions import NotFoundError

class TestUserService:
    """Test suite for UserService."""

    def test_get_user_returns_user_when_exists(self, user_service, sample_user):
        """Should return user when ID exists."""
        # Arrange - setup is in fixtures

        # Act
        result = user_service.get_by_id(sample_user.id)

        # Assert
        assert result.id == sample_user.id
        assert result.email == sample_user.email

    def test_get_user_raises_not_found_when_missing(self, user_service):
        """Should raise NotFoundError for non-existent ID."""
        with pytest.raises(NotFoundError) as exc_info:
            user_service.get_by_id("non-existent-id")

        assert "not found" in str(exc_info.value).lower()
```

### Naming Conventions

```python
# ✅ GOOD: Descriptive test names
def test_calculate_total_returns_zero_for_empty_cart():
    pass

def test_validate_email_raises_value_error_for_invalid_format():
    pass

def test_user_service_creates_user_with_hashed_password():
    pass

# ❌ BAD: Vague names
def test_calculate():
    pass

def test_validate():
    pass

def test_user():
    pass
```

## Fixtures

### Basic Fixtures

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.rollback()
    session.close()

@pytest.fixture
def user_service(db_session):
    """Create UserService with test database."""
    from app.repositories.user_repository import UserRepository
    from app.services.user_service import UserService

    repo = UserRepository(db_session)
    return UserService(repo)

@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    from app.models.user import User

    user = User(
        id="test-user-123",
        email="test@example.com",
        name="Test User"
    )
    db_session.add(user)
    db_session.commit()

    return user
```

### Fixture Scopes

```python
@pytest.fixture(scope="session")
def database_engine():
    """Create engine once per test session."""
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()

@pytest.fixture(scope="module")
def test_client(app):
    """Create test client once per module."""
    return TestClient(app)

@pytest.fixture(scope="function")  # default
def clean_database(db_session):
    """Clean database for each test."""
    yield
    db_session.rollback()

@pytest.fixture(scope="class")
def shared_state():
    """Share state across tests in a class."""
    return {"counter": 0}
```

### Parametrized Fixtures

```python
@pytest.fixture(params=["sqlite", "postgresql"])
def db_engine(request):
    """Test with multiple database backends."""
    if request.param == "sqlite":
        return create_engine("sqlite:///:memory:")
    else:
        return create_engine("postgresql://test@localhost/test")
```

## Mocking

### Using pytest-mock

```python
def test_send_email_calls_smtp_service(mocker):
    """Should call SMTP service with correct parameters."""
    # Arrange
    mock_smtp = mocker.patch("app.services.email.smtp_client")
    email_service = EmailService()

    # Act
    email_service.send("test@example.com", "Hello", "Body")

    # Assert
    mock_smtp.send_message.assert_called_once()
    call_args = mock_smtp.send_message.call_args[0][0]
    assert call_args["to"] == "test@example.com"

def test_user_service_with_mocked_repository(mocker):
    """Should use repository correctly."""
    # Create mock repository
    mock_repo = mocker.Mock()
    mock_repo.find_by_id.return_value = User(id="1", email="test@test.com")

    service = UserService(mock_repo)
    result = service.get_by_id("1")

    mock_repo.find_by_id.assert_called_once_with("1")
    assert result.email == "test@test.com"
```

### Mocking External Services

```python
@pytest.fixture
def mock_external_api(mocker):
    """Mock external API responses."""
    mock = mocker.patch("app.clients.external_api.fetch")
    mock.return_value = {
        "status": "success",
        "data": {"id": 123, "name": "Test"}
    }
    return mock

def test_integration_with_external_api(mock_external_api):
    """Should process external API response correctly."""
    service = IntegrationService()
    result = service.fetch_and_process(123)

    assert result.name == "Test"
    mock_external_api.assert_called_once_with(123)
```

### AsyncIO Mocking

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_service(mocker):
    """Test async functions with AsyncMock."""
    mock_client = mocker.patch("app.clients.async_client.fetch")
    mock_client.return_value = AsyncMock(return_value={"data": "test"})

    service = AsyncService()
    result = await service.get_data()

    assert result["data"] == "test"
```

## Parametrized Tests

```python
@pytest.mark.parametrize("input_value,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("PyTest", "PYTEST"),
    ("", ""),
])
def test_uppercase_conversion(input_value, expected):
    """Test uppercase for various inputs."""
    assert input_value.upper() == expected

@pytest.mark.parametrize("email,is_valid", [
    ("user@example.com", True),
    ("user@domain.org", True),
    ("invalid-email", False),
    ("@nodomain.com", False),
    ("user@", False),
    ("", False),
])
def test_email_validation(email, is_valid):
    """Test email validation for edge cases."""
    from app.validators import is_valid_email
    assert is_valid_email(email) == is_valid
```

## Exception Testing

```python
def test_raises_value_error_for_negative_amount():
    """Should raise ValueError for negative amounts."""
    with pytest.raises(ValueError) as exc_info:
        process_payment(-100)

    assert "negative" in str(exc_info.value).lower()

def test_raises_custom_exception_with_details():
    """Should raise custom exception with error code."""
    with pytest.raises(PaymentError) as exc_info:
        process_payment(0)

    error = exc_info.value
    assert error.code == "INVALID_AMOUNT"
    assert error.message == "Amount must be positive"
```

## Test Organization

### conftest.py Structure

```python
# tests/conftest.py - Shared fixtures
import pytest
from app import create_app
from app.database import init_db

@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    app = create_app("testing")
    return app

@pytest.fixture(scope="session")
def database(app):
    """Initialize test database."""
    with app.app_context():
        init_db()
        yield
        # cleanup

# tests/unit/conftest.py - Unit test specific
@pytest.fixture
def mock_services(mocker):
    """Mock all external services."""
    return {
        "email": mocker.patch("app.services.email"),
        "payment": mocker.patch("app.services.payment"),
    }

# tests/integration/conftest.py - Integration test specific
@pytest.fixture
def test_client(app):
    """Create test client for API testing."""
    return app.test_client()
```

### Directory Structure

```
tests/
├── conftest.py           # Shared fixtures
├── unit/
│   ├── conftest.py       # Unit test fixtures
│   ├── test_services.py
│   └── test_models.py
├── integration/
│   ├── conftest.py       # Integration fixtures
│   └── test_api.py
└── e2e/
    ├── conftest.py       # E2E fixtures
    └── test_workflows.py
```

## Coverage Best Practices

### pytest.ini Configuration

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
filterwarnings =
    ignore::DeprecationWarning
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific markers
pytest -m "not slow"
pytest -m integration

# Run in parallel
pytest -n auto

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## Quick Reference

| Pattern | Use Case | Example |
|---------|----------|---------|
| `@pytest.fixture` | Setup/teardown | Database sessions |
| `@pytest.mark.parametrize` | Multiple inputs | Validation tests |
| `pytest.raises()` | Exception testing | Error handling |
| `mocker.patch()` | Mocking | External services |
| `@pytest.mark.asyncio` | Async tests | Async functions |
| `conftest.py` | Shared fixtures | Cross-module fixtures |

## Checklist

Before submitting tests:
- [ ] Tests have descriptive names (what + expected behavior)
- [ ] Each test has clear Arrange/Act/Assert sections
- [ ] Fixtures are used for setup, not repeated code
- [ ] Edge cases are covered (empty, null, boundary values)
- [ ] Mocks verify called with correct parameters
- [ ] Coverage is above minimum threshold (80%+)
- [ ] Tests run independently (no order dependency)

**Remember**: Good tests document behavior. If someone reads your test, they should understand what the code does!

---

## debugging-strategies

# Debugging Strategies

## Purpose

This skill provides systematic debugging techniques, profiling tools, and root cause analysis approaches to efficiently track down bugs across any codebase or technology stack.

## When This Skill Activates

- Keywords: debug, bug, error, issue, traceback, exception, not working, fix
- Error messages in conversation
- Investigating unexpected behavior
- Performance issues or crashes

## The Debugging Mindset

### Rule #1: Reproduce Before You Fix

**NEVER fix what you can't reproduce.**

```python
# ❌ BAD: "I think I fixed it"
# Changed random things hoping it works

# ✅ GOOD: Clear reproduction steps
"""
Bug: User login fails silently

Steps to reproduce:
1. Go to /login
2. Enter email: test@example.com (valid)
3. Enter password: Test123! (valid)
4. Click "Login"
5. Expected: Redirect to dashboard
6. Actual: Page refreshes, no error shown

Environment: Chrome 120, Ubuntu 22.04
Frequency: 100% reproducible
"""
```

### The 5 Whys Technique

```
Problem: API returns 500 error

Why #1: Database query failed
Why #2: Connection pool exhausted
Why #3: Connections not being released
Why #4: Exception handler not closing connection
Why #5: Missing finally block in try/except

Root Cause: Missing connection cleanup in error paths
Fix: Add finally block to release connection
```

## Systematic Debugging Process

### Step 1: Gather Information

```python
# Collect all relevant data:
# 1. Full error message and stack trace
# 2. Input that caused the error
# 3. Environment (OS, Python version, dependencies)
# 4. Recent changes (git log, git diff)
# 5. Frequency (always, intermittent, specific conditions)

# Log everything:
import logging
import traceback

logger = logging.getLogger(__name__)

try:
    result = process_data(input_data)
except Exception as e:
    logger.error(
        "process_data failed",
        extra={
            "input_data": input_data,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
        }
    )
    raise
```

### Step 2: Isolate the Problem

```python
# Binary search debugging - divide and conquer

def complex_pipeline(data):
    step1 = preprocess(data)
    print(f"After step1: {step1}")  # Checkpoint 1

    step2 = transform(step1)
    print(f"After step2: {step2}")  # Checkpoint 2

    step3 = validate(step2)
    print(f"After step3: {step3}")  # Checkpoint 3

    return finalize(step3)

# If error occurs after step2, problem is in transform() or validate()
# Add more checkpoints to narrow down
```

### Step 3: Form a Hypothesis

```python
# Based on evidence, form testable hypothesis:

# Hypothesis: "The bug occurs because user_id is None
# when the user hasn't completed onboarding"

# Test:
def get_user_profile(user_id):
    # Add validation to test hypothesis
    if user_id is None:
        logger.warning("user_id is None - hypothesis confirmed!")
        raise ValueError("user_id cannot be None")

    return db.get_user(user_id)
```

### Step 4: Test and Verify

```python
# After fixing, verify:
# 1. Original bug is fixed
# 2. No new bugs introduced
# 3. Edge cases handled

def test_bug_fix_regression():
    """Verify the specific bug is fixed."""
    # Reproduce original conditions
    result = function_that_was_broken(problematic_input)

    # Verify correct behavior
    assert result == expected_output

def test_edge_cases_after_fix():
    """Verify edge cases still work."""
    assert function_that_was_broken(None) raises ValueError
    assert function_that_was_broken("") == default_value
```

## Python Debugging Tools

### Using pdb (Python Debugger)

```python
# Insert breakpoint
import pdb; pdb.set_trace()  # Python 3.6 and earlier

breakpoint()  # Python 3.7+ (preferred)

# Common pdb commands:
# n (next)     - Execute next line
# s (step)     - Step into function
# c (continue) - Continue until next breakpoint
# p variable  - Print variable value
# pp variable - Pretty print
# l (list)    - Show current code
# w (where)   - Show call stack
# q (quit)    - Quit debugger
```

### Using ipdb (Enhanced pdb)

```python
# Better debugging experience
import ipdb; ipdb.set_trace()

# Features:
# - Syntax highlighting
# - Tab completion
# - Better stack traces
```

### Logging for Debugging

```python
import logging

# Configure for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def process_order(order):
    logger.debug(f"Processing order: {order.id}")
    logger.debug(f"Order items: {order.items}")

    for item in order.items:
        logger.debug(f"Processing item: {item.name}")
        try:
            result = process_item(item)
            logger.info(f"Item {item.name} processed successfully")
        except Exception as e:
            logger.error(f"Failed to process {item.name}: {e}")
            raise

    logger.info(f"Order {order.id} completed")
```

### Using traceback Module

```python
import traceback

def debug_exception():
    try:
        risky_operation()
    except Exception as e:
        # Print full traceback
        traceback.print_exc()

        # Get traceback as string
        tb_str = traceback.format_exc()
        logger.error(f"Full traceback:\n{tb_str}")

        # Get just the exception info
        exc_type, exc_value, exc_tb = sys.exc_info()
        logger.error(f"Exception type: {exc_type}")
        logger.error(f"Exception value: {exc_value}")
```

## Common Bug Patterns

### Off-by-One Errors

```python
# ❌ BUG: Missing last element
for i in range(len(items) - 1):  # Should be len(items)
    process(items[i])

# ❌ BUG: Index out of bounds
for i in range(1, len(items) + 1):  # Should start at 0
    print(items[i])

# ✅ CORRECT
for item in items:  # Prefer iteration over indexing
    process(item)
```

### None/Null Reference

```python
# ❌ BUG: Not handling None
def get_user_email(user_id):
    user = db.get_user(user_id)
    return user.email  # Crashes if user is None

# ✅ CORRECT
def get_user_email(user_id):
    user = db.get_user(user_id)
    if user is None:
        return None  # or raise exception
    return user.email
```

### Race Conditions

```python
# ❌ BUG: Race condition
counter = 0
def increment():
    global counter
    counter = counter + 1  # Not atomic!

# ✅ CORRECT: Use locks
import threading
lock = threading.Lock()
counter = 0

def increment():
    global counter
    with lock:
        counter = counter + 1
```

### Mutable Default Arguments

```python
# ❌ BUG: Mutable default
def add_item(item, items=[]):  # Same list shared!
    items.append(item)
    return items

# ✅ CORRECT
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

## Debugging Checklist

When encountering a bug:

1. **Reproduce**
   - [ ] Can you reproduce the bug consistently?
   - [ ] What are the exact steps?
   - [ ] What environment?

2. **Gather Evidence**
   - [ ] Full error message/stack trace
   - [ ] Relevant logs
   - [ ] Recent code changes (git diff)

3. **Isolate**
   - [ ] Which component/function fails?
   - [ ] What input causes it?
   - [ ] Is it always or intermittent?

4. **Hypothesize**
   - [ ] What do you think is wrong?
   - [ ] How can you test this theory?

5. **Fix**
   - [ ] Minimal change that fixes the issue
   - [ ] Does it break anything else?

6. **Verify**
   - [ ] Bug is fixed
   - [ ] Add regression test
   - [ ] Document the fix

## Quick Reference

| Tool | Use Case | Command |
|------|----------|---------|
| `breakpoint()` | Interactive debugging | Insert in code |
| `logging` | Track execution flow | `logger.debug()` |
| `traceback` | Full error context | `traceback.print_exc()` |
| `pdb` | Step through code | `n`, `s`, `c`, `p` |
| `git bisect` | Find breaking commit | `git bisect start` |
| `strace` | System call tracing | `strace python app.py` |

**Remember**: Debugging is detective work. Follow the evidence, form hypotheses, and test them systematically!

---

## python-performance-optimization

# Python Performance Optimization

## Purpose

This skill provides techniques for profiling and optimizing Python code using cProfile, memory profilers, and performance best practices to identify and fix bottlenecks.

## When This Skill Activates

- Keywords: slow, performance, optimize, profile, bottleneck, memory, speed
- Editing performance-critical code
- Investigating slow operations
- Memory usage issues

## Profiling First, Optimize Second

**Golden Rule**: Never optimize without profiling first.

```python
# ❌ BAD: Premature optimization
def process_data(items):
    # "I think list comprehension is faster"
    return [expensive_operation(x) for x in items]

# ✅ GOOD: Profile first
import cProfile

# Profile to find actual bottlenecks
cProfile.run('process_data(sample_data)')

# Then optimize based on evidence
```

## cProfile Usage

### Basic Profiling

```python
import cProfile
import pstats

# Profile a function
def profile_function():
    cProfile.run('my_function()', 'output.prof')

    # Analyze results
    stats = pstats.Stats('output.prof')
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # Top 10 functions

# Profile a code block
profiler = cProfile.Profile()
profiler.enable()

# Your code here
result = complex_operation()

profiler.disable()
profiler.print_stats(sort='cumulative')
```

### Using as Decorator

```python
import cProfile
import functools

def profile(func):
    """Decorator to profile a function."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()
        profiler.print_stats(sort='cumulative')
        return result
    return wrapper

@profile
def my_slow_function():
    # ... function code
    pass
```

## Memory Profiling

### Using memory_profiler

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # This will show memory usage line by line
    data = [i ** 2 for i in range(1000000)]
    filtered = [x for x in data if x % 2 == 0]
    return sum(filtered)

# Run with: python -m memory_profiler script.py
```

### Using tracemalloc

```python
import tracemalloc

tracemalloc.start()

# Your code here
result = process_large_dataset()

snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

print("Top 10 memory allocations:")
for stat in top_stats[:10]:
    print(stat)
```

## Common Optimizations

### Use Generators Instead of Lists

```python
# ❌ SLOW: Creates full list in memory
def get_all_squares(n):
    return [x ** 2 for x in range(n)]

# ✅ FAST: Generates values lazily
def get_all_squares(n):
    return (x ** 2 for x in range(n))

# Usage - only computes what's needed
for square in get_all_squares(10000000):
    if square > 1000:
        break
```

### Use Built-in Functions

```python
# ❌ SLOW: Manual loop
total = 0
for x in numbers:
    total += x

# ✅ FAST: Built-in function (implemented in C)
total = sum(numbers)

# ❌ SLOW: Manual maximum
max_val = numbers[0]
for x in numbers[1:]:
    if x > max_val:
        max_val = x

# ✅ FAST: Built-in
max_val = max(numbers)
```

### Dictionary Lookups vs List Searches

```python
# ❌ SLOW: O(n) for each lookup
def find_user(user_id, users_list):
    for user in users_list:
        if user['id'] == user_id:
            return user
    return None

# ✅ FAST: O(1) lookup
def find_user(user_id, users_dict):
    return users_dict.get(user_id)

# Convert list to dict once
users_dict = {user['id']: user for user in users_list}
```

### String Concatenation

```python
# ❌ SLOW: Creates new string each iteration
result = ""
for item in items:
    result += str(item)

# ✅ FAST: Join is optimized
result = "".join(str(item) for item in items)

# ✅ FAST: For f-strings with few items
result = f"{item1}{item2}{item3}"
```

### Cache Expensive Operations

```python
from functools import lru_cache

# ✅ GOOD: Cache results of expensive function
@lru_cache(maxsize=1000)
def expensive_calculation(n):
    # Complex computation
    return result

# For methods that depend on self
from functools import cached_property

class DataProcessor:
    @cached_property
    def processed_data(self):
        # Computed once, cached
        return self._expensive_processing()
```

### Use Local Variables

```python
# ❌ SLOWER: Global lookup each iteration
import math

def compute(values):
    return [math.sqrt(x) for x in values]

# ✅ FASTER: Local reference
def compute(values):
    sqrt = math.sqrt  # Local reference
    return [sqrt(x) for x in values]
```

### Avoid Repeated Attribute Lookups

```python
# ❌ SLOW: Multiple attribute lookups
for item in items:
    self.data.results.append(item.value)

# ✅ FAST: Cache the reference
results = self.data.results
append = results.append
for item in items:
    append(item.value)
```

## NumPy Optimizations

```python
import numpy as np

# ❌ SLOW: Python loop
def add_arrays_slow(a, b):
    result = []
    for i in range(len(a)):
        result.append(a[i] + b[i])
    return result

# ✅ FAST: Vectorized NumPy
def add_arrays_fast(a, b):
    return np.array(a) + np.array(b)

# ✅ EVEN FASTER: Keep as NumPy arrays
a = np.array([1, 2, 3, 4, 5])
b = np.array([6, 7, 8, 9, 10])
result = a + b
```

## Async for I/O Operations

```python
import asyncio
import aiohttp

# ❌ SLOW: Sequential I/O
def fetch_all_sync(urls):
    results = []
    for url in urls:
        response = requests.get(url)
        results.append(response.json())
    return results

# ✅ FAST: Concurrent I/O
async def fetch_all_async(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_one(session, url) for url in urls]
        return await asyncio.gather(*tasks)

async def fetch_one(session, url):
    async with session.get(url) as response:
        return await response.json()
```

## Quick Wins Checklist

Before deep optimization:
- [ ] Profile to find actual bottlenecks
- [ ] Use built-in functions (`sum`, `max`, `min`, `sorted`)
- [ ] Replace lists with generators where possible
- [ ] Use dict/set for O(1) lookups instead of list search
- [ ] Use `"".join()` instead of `+=` for strings
- [ ] Add `@lru_cache` to pure functions with repeated calls
- [ ] Use local variables in tight loops
- [ ] Consider NumPy for numerical operations
- [ ] Use async for I/O-bound operations

## Quick Reference

| Bottleneck | Solution |
|------------|----------|
| Slow loops | Use comprehensions, generators |
| Repeated calculations | `@lru_cache`, `@cached_property` |
| String building | `"".join()` |
| List searches | Convert to dict/set |
| Memory issues | Use generators |
| I/O bound | Use async/await |
| CPU bound | Use multiprocessing |
| Numerical | Use NumPy/Pandas |

**Remember**: Measure, don't guess. Profile first, then optimize the proven bottlenecks!

---

# API e Arquitetura

---

## api-design-principles

# API Design Principles

## Purpose

This skill provides comprehensive patterns for designing REST and GraphQL APIs that are intuitive, scalable, and maintainable, following industry best practices.

## When This Skill Activates

- Keywords: API, REST, GraphQL, endpoint, route, resource, HTTP
- Editing API routes or controllers
- Designing new APIs
- Reviewing API specifications

## REST API Design

### Resource Naming

```python
# ✅ GOOD: Plural nouns for resources
GET /users
GET /users/{id}
POST /users
PUT /users/{id}
DELETE /users/{id}

# ✅ GOOD: Nested resources show relationships
GET /users/{id}/orders
GET /orders/{id}/items

# ❌ BAD: Verbs in URLs
GET /getUsers
POST /createUser
GET /fetchAllOrders

# ❌ BAD: Inconsistent naming
GET /user        # Should be /users
GET /order-list  # Should be /orders
```

### HTTP Methods

| Method | Purpose | Idempotent | Safe | Request Body |
|--------|---------|------------|------|--------------|
| GET | Read resource | Yes | Yes | No |
| POST | Create resource | No | No | Yes |
| PUT | Replace resource | Yes | No | Yes |
| PATCH | Partial update | Yes | No | Yes |
| DELETE | Remove resource | Yes | No | Optional |

```python
# FastAPI Example
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}")
async def get_user(user_id: str):
    """GET - Read a user."""
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user

@router.post("/", status_code=201)
async def create_user(user: UserCreate):
    """POST - Create a new user."""
    return await user_service.create(user)

@router.put("/{user_id}")
async def replace_user(user_id: str, user: UserUpdate):
    """PUT - Replace entire user resource."""
    return await user_service.replace(user_id, user)

@router.patch("/{user_id}")
async def update_user(user_id: str, user: UserPatch):
    """PATCH - Partial update."""
    return await user_service.update(user_id, user)

@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str):
    """DELETE - Remove user."""
    await user_service.delete(user_id)
    return None
```

### HTTP Status Codes

```python
# Success responses
200 OK          # Successful GET, PUT, PATCH
201 Created     # Successful POST (include Location header)
204 No Content  # Successful DELETE

# Client errors
400 Bad Request    # Invalid input
401 Unauthorized   # Missing or invalid authentication
403 Forbidden      # Authenticated but not authorized
404 Not Found      # Resource doesn't exist
409 Conflict       # Resource conflict (e.g., duplicate)
422 Unprocessable  # Validation error

# Server errors
500 Internal       # Unexpected server error
503 Unavailable    # Service temporarily down
```

### Pagination

```python
# ✅ GOOD: Cursor-based pagination (performant for large datasets)
GET /users?cursor=eyJpZCI6MTIzfQ&limit=20

# Response
{
    "data": [...],
    "pagination": {
        "next_cursor": "eyJpZCI6MTQzfQ",
        "has_more": true
    }
}

# ✅ GOOD: Offset pagination (simple, allows jumping)
GET /users?page=3&per_page=20

# Response
{
    "data": [...],
    "pagination": {
        "page": 3,
        "per_page": 20,
        "total": 157,
        "total_pages": 8
    }
}

# FastAPI implementation
@router.get("/")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    offset = (page - 1) * per_page
    users = await user_service.list(offset=offset, limit=per_page)
    total = await user_service.count()

    return {
        "data": users,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    }
```

### Filtering and Sorting

```python
# ✅ GOOD: Clear query parameters
GET /users?status=active&role=admin
GET /users?created_after=2024-01-01
GET /orders?sort=created_at&order=desc

# FastAPI implementation
@router.get("/")
async def list_users(
    status: Optional[str] = None,
    role: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|name|email)$"),
    order: str = Query("desc", regex="^(asc|desc)$"),
):
    filters = {}
    if status:
        filters["status"] = status
    if role:
        filters["role"] = role

    return await user_service.list(
        filters=filters,
        sort_by=sort_by,
        order=order
    )
```

### Error Response Format

```python
# ✅ GOOD: Consistent error format
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input provided",
        "details": [
            {
                "field": "email",
                "message": "Must be a valid email address"
            },
            {
                "field": "age",
                "message": "Must be at least 18"
            }
        ]
    }
}

# FastAPI implementation
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input provided",
                "details": [
                    {"field": e["loc"][-1], "message": e["msg"]}
                    for e in exc.errors()
                ]
            }
        }
    )
```

### Versioning

```python
# ✅ GOOD: URL path versioning (most common)
/api/v1/users
/api/v2/users

# Alternative: Header versioning
Accept: application/vnd.myapi.v2+json

# FastAPI implementation
app = FastAPI()

# Version 1
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(users_v1.router)

# Version 2
v2_router = APIRouter(prefix="/api/v2")
v2_router.include_router(users_v2.router)

app.include_router(v1_router)
app.include_router(v2_router)
```

## API Security

### Authentication

```python
# ✅ GOOD: Bearer token authentication
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = await verify_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

### Rate Limiting

```python
# ✅ GOOD: Rate limit responses
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1609459200

# FastAPI implementation with slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get("/users")
@limiter.limit("100/minute")
async def list_users(request: Request):
    return await user_service.list()
```

## Quick Reference

| Principle | Guideline |
|-----------|-----------|
| Resources | Use plural nouns (`/users`, `/orders`) |
| URLs | Keep flat, max 2-3 levels deep |
| HTTP Methods | Use correctly (GET=read, POST=create, etc.) |
| Status Codes | Return appropriate codes |
| Pagination | Always paginate lists |
| Filtering | Use query parameters |
| Errors | Consistent error format |
| Versioning | Version from day one |

## API Design Checklist

Before shipping an API:
- [ ] Resources use plural nouns
- [ ] HTTP methods used correctly
- [ ] Proper status codes returned
- [ ] Error responses are consistent
- [ ] Pagination implemented for lists
- [ ] Authentication/authorization in place
- [ ] Rate limiting configured
- [ ] API is versioned
- [ ] Documentation is complete

**Remember**: Your API is a product. Design it for the developers who will use it!

---

## llm-evaluation

# LLM Evaluation

## Purpose

This skill provides comprehensive strategies for evaluating LLM applications using automated metrics, human feedback, and benchmarking to ensure quality and reliability.

## When This Skill Activates

- Keywords: evaluate, benchmark, metric, quality, hallucination, accuracy
- Editing LLM-related code in `/agents/`, `/evaluation/`
- Testing LLM outputs
- Measuring AI application quality

## Evaluation Dimensions

### 1. Answer Relevance

Does the response address the user's question?

```python
from openai import OpenAI

def evaluate_relevance(question: str, answer: str) -> float:
    """Use LLM-as-judge to score relevance (0-1)."""
    client = OpenAI()

    prompt = f"""Rate how well this answer addresses the question.

Question: {question}
Answer: {answer}

Score from 0.0 to 1.0 where:
- 1.0 = Directly and completely answers the question
- 0.5 = Partially addresses the question
- 0.0 = Does not address the question at all

Return ONLY a number between 0.0 and 1.0."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return float(response.choices[0].message.content.strip())
```

### 2. Faithfulness (Hallucination Detection)

Is the response grounded in provided context?

```python
def evaluate_faithfulness(context: str, answer: str) -> dict:
    """Check if answer is supported by context."""
    prompt = f"""Analyze if the following answer is fully supported by the context.

Context:
{context}

Answer:
{answer}

For each claim in the answer, determine if it is:
- SUPPORTED: Directly stated or clearly implied by context
- NOT_SUPPORTED: Not found in context (potential hallucination)

Return JSON with:
{{"faithfulness_score": 0.0-1.0, "unsupported_claims": [...]}}"""

    # Call LLM and parse response
    response = call_llm(prompt)
    return json.loads(response)

# Example usage
result = evaluate_faithfulness(
    context="MedSafe analyzes drug interactions using AI.",
    answer="MedSafe uses machine learning to detect dangerous drug combinations and was founded in 2020."
)
# Returns: {"faithfulness_score": 0.5, "unsupported_claims": ["founded in 2020"]}
```

### 3. Correctness

Is the answer factually correct?

```python
def evaluate_correctness(
    question: str,
    answer: str,
    ground_truth: str
) -> dict:
    """Compare answer against ground truth."""
    prompt = f"""Compare the answer to the ground truth.

Question: {question}
Ground Truth: {ground_truth}
Answer: {answer}

Evaluate:
1. Are the key facts correct?
2. Is any information missing?
3. Is there any incorrect information?

Return JSON:
{{"correctness_score": 0.0-1.0, "missing_info": [...], "incorrect_info": [...]}}"""

    response = call_llm(prompt)
    return json.loads(response)
```

### 4. Context Precision/Recall

For RAG systems: Are we retrieving the right documents?

```python
def evaluate_retrieval(
    query: str,
    retrieved_docs: list[str],
    relevant_docs: list[str]
) -> dict:
    """Evaluate retrieval quality."""
    retrieved_set = set(retrieved_docs)
    relevant_set = set(relevant_docs)

    # Precision: What fraction of retrieved docs are relevant?
    true_positives = len(retrieved_set & relevant_set)
    precision = true_positives / len(retrieved_set) if retrieved_set else 0

    # Recall: What fraction of relevant docs were retrieved?
    recall = true_positives / len(relevant_set) if relevant_set else 0

    # F1 Score
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1
    }
```

## Automated Metrics

### Semantic Similarity

```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

def semantic_similarity(text1: str, text2: str) -> float:
    """Calculate semantic similarity between two texts."""
    model = SentenceTransformer('all-MiniLM-L6-v2')

    embeddings = model.encode([text1, text2])
    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]

    return float(similarity)

# Usage
score = semantic_similarity(
    "The medication is contraindicated for patients with liver disease",
    "Patients with hepatic conditions should not take this drug"
)
# Returns: ~0.85 (high similarity despite different words)
```

### Response Length

```python
def evaluate_response_length(
    response: str,
    min_length: int = 50,
    max_length: int = 500
) -> dict:
    """Check if response length is appropriate."""
    length = len(response)
    words = len(response.split())

    is_too_short = length < min_length
    is_too_long = length > max_length

    return {
        "char_count": length,
        "word_count": words,
        "is_appropriate": not (is_too_short or is_too_long),
        "issue": "too_short" if is_too_short else ("too_long" if is_too_long else None)
    }
```

### Toxicity/Safety

```python
def check_safety(response: str) -> dict:
    """Check response for safety issues."""
    prompt = f"""Analyze this response for safety issues:

Response: {response}

Check for:
1. Medical misinformation that could harm patients
2. Dangerous drug recommendations
3. Inappropriate content
4. Bias or discriminatory content

Return JSON:
{{"is_safe": true/false, "issues": [...]}}"""

    result = call_llm(prompt)
    return json.loads(result)
```

## Evaluation Pipeline

### Complete Evaluation Function

```python
class LLMEvaluator:
    """Comprehensive LLM evaluation pipeline."""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def evaluate(
        self,
        question: str,
        response: str,
        context: str = None,
        ground_truth: str = None
    ) -> dict:
        """Run full evaluation suite."""
        results = {
            "question": question,
            "response": response,
            "metrics": {}
        }

        # 1. Relevance (always)
        results["metrics"]["relevance"] = await self.evaluate_relevance(
            question, response
        )

        # 2. Faithfulness (if context provided)
        if context:
            results["metrics"]["faithfulness"] = await self.evaluate_faithfulness(
                context, response
            )

        # 3. Correctness (if ground truth provided)
        if ground_truth:
            results["metrics"]["correctness"] = await self.evaluate_correctness(
                question, response, ground_truth
            )

        # 4. Safety (always)
        results["metrics"]["safety"] = await self.check_safety(response)

        # 5. Response quality
        results["metrics"]["length"] = self.evaluate_response_length(response)

        # Calculate overall score
        scores = [
            v.get("score", v) for v in results["metrics"].values()
            if isinstance(v, (int, float)) or isinstance(v, dict) and "score" in v
        ]
        results["overall_score"] = sum(scores) / len(scores) if scores else 0

        return results
```

### Batch Evaluation

```python
async def run_benchmark(
    evaluator: LLMEvaluator,
    test_cases: list[dict]
) -> dict:
    """Run evaluation on a benchmark dataset."""
    results = []

    for case in test_cases:
        result = await evaluator.evaluate(
            question=case["question"],
            response=case["response"],
            context=case.get("context"),
            ground_truth=case.get("expected_answer")
        )
        results.append(result)

    # Aggregate metrics
    aggregated = {
        "total_cases": len(results),
        "avg_relevance": sum(r["metrics"]["relevance"] for r in results) / len(results),
        "avg_overall": sum(r["overall_score"] for r in results) / len(results),
        "safety_pass_rate": sum(1 for r in results if r["metrics"]["safety"]["is_safe"]) / len(results)
    }

    return {
        "individual_results": results,
        "aggregated_metrics": aggregated
    }
```

## Creating Benchmark Datasets

```python
# benchmark_dataset.json
{
    "name": "MedSafe Drug Interaction Benchmark",
    "version": "1.0",
    "test_cases": [
        {
            "id": "DI001",
            "difficulty": "easy",
            "question": "What is the interaction between warfarin and aspirin?",
            "context": "Warfarin and aspirin both affect blood clotting...",
            "expected_answer": "Concurrent use increases bleeding risk significantly...",
            "tags": ["anticoagulant", "nsaid", "bleeding_risk"]
        },
        {
            "id": "DI002",
            "difficulty": "hard",
            "question": "How does metformin interact with contrast dye?",
            "context": "Metformin is contraindicated with iodinated contrast...",
            "expected_answer": "Risk of lactic acidosis; stop metformin 48h before...",
            "tags": ["diabetes", "imaging", "kidney"]
        }
    ]
}
```

## A/B Testing LLM Changes

```python
async def ab_test_models(
    model_a: str,
    model_b: str,
    test_cases: list[dict]
) -> dict:
    """Compare two models on same test cases."""
    results_a = []
    results_b = []

    for case in test_cases:
        # Get response from model A
        response_a = await get_llm_response(model_a, case["question"])
        eval_a = await evaluate(case["question"], response_a, case.get("ground_truth"))
        results_a.append(eval_a)

        # Get response from model B
        response_b = await get_llm_response(model_b, case["question"])
        eval_b = await evaluate(case["question"], response_b, case.get("ground_truth"))
        results_b.append(eval_b)

    return {
        "model_a": {
            "name": model_a,
            "avg_score": sum(r["overall_score"] for r in results_a) / len(results_a)
        },
        "model_b": {
            "name": model_b,
            "avg_score": sum(r["overall_score"] for r in results_b) / len(results_b)
        },
        "winner": "model_a" if results_a > results_b else "model_b"
    }
```

## Continuous Monitoring

```python
from prometheus_client import Counter, Histogram

# Metrics
llm_response_quality = Histogram(
    'llm_response_quality_score',
    'LLM response quality score',
    ['model', 'task_type']
)

llm_hallucination_count = Counter(
    'llm_hallucinations_total',
    'Number of detected hallucinations',
    ['model']
)

async def monitored_llm_call(model: str, prompt: str) -> dict:
    """Make LLM call with automatic quality monitoring."""
    response = await call_llm(model, prompt)

    # Evaluate response
    evaluation = await quick_evaluate(prompt, response)

    # Record metrics
    llm_response_quality.labels(
        model=model,
        task_type="general"
    ).observe(evaluation["quality_score"])

    if not evaluation["is_grounded"]:
        llm_hallucination_count.labels(model=model).inc()

    return {
        "response": response,
        "evaluation": evaluation
    }
```

## Quick Reference

| Metric | Measures | When to Use |
|--------|----------|-------------|
| Relevance | Does answer address question? | Always |
| Faithfulness | Is answer grounded in context? | RAG systems |
| Correctness | Is answer factually correct? | With ground truth |
| Similarity | How close to expected answer? | Comparison |
| Safety | Is answer safe/appropriate? | Always |
| Latency | Response time | Performance |

## Evaluation Checklist

Before deploying LLM features:
- [ ] Benchmark dataset created with diverse cases
- [ ] Relevance evaluation implemented
- [ ] Hallucination detection in place
- [ ] Safety checks configured
- [ ] A/B testing framework ready
- [ ] Continuous monitoring enabled
- [ ] Human evaluation process defined

**Remember**: Evaluate early, evaluate often. LLM quality can drift!

---

# DevOps e Infraestrutura

---

## github-actions-templates

# GitHub Actions Templates

## Purpose

This skill provides production-ready GitHub Actions workflow templates for CI/CD pipelines, automated testing, building, and deployment.

## When This Skill Activates

- Keywords: GitHub Actions, CI/CD, workflow, pipeline, deploy
- Editing `.github/workflows/*.yml` files
- Setting up continuous integration
- Creating deployment pipelines

## CI Workflow Template

### Python Testing Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-test.txt

      - name: Run linting
        run: |
          ruff check .
          ruff format --check .

      - name: Run type checking
        run: mypy backend/

      - name: Run tests with coverage
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test_db
          TESTING: "true"
        run: |
          pytest --cov=backend --cov-report=xml --cov-report=term-missing

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          fail_ci_if_error: true

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run security scan
        uses: pyupio/safety@v2
        with:
          api-key: ${{ secrets.SAFETY_API_KEY }}

      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r backend/ -ll
```

### Build Workflow

```yaml
# .github/workflows/build.yml
name: Build

on:
  push:
    branches: [main]
    tags: ['v*']

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=sha,prefix=

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### Deploy Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  workflow_run:
    workflows: [Build]
    types: [completed]
    branches: [main]

jobs:
  deploy-staging:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    environment: staging

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to staging
        run: |
          # Deploy script here
          echo "Deploying to staging..."

      - name: Run smoke tests
        run: |
          curl -f https://staging.example.com/healthz || exit 1

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://example.com

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to production
        run: |
          echo "Deploying to production..."

      - name: Verify deployment
        run: |
          curl -f https://example.com/healthz || exit 1
```

## Reusable Workflows

```yaml
# .github/workflows/reusable-test.yml
name: Reusable Test Workflow

on:
  workflow_call:
    inputs:
      python-version:
        required: false
        type: string
        default: "3.11"
    secrets:
      codecov-token:
        required: false

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ inputs.python-version }}
          cache: 'pip'

      - name: Run tests
        run: pytest --cov
```

## Quick Reference

| Action | Use Case |
|--------|----------|
| `actions/checkout@v4` | Clone repository |
| `actions/setup-python@v5` | Setup Python |
| `docker/build-push-action@v5` | Build/push Docker |
| `codecov/codecov-action@v4` | Upload coverage |

**Remember**: Keep workflows DRY with reusable workflows and composite actions!

---

## prometheus-configuration

# Prometheus Configuration

## Purpose

This skill provides patterns for setting up Prometheus for metric collection, alerting, and monitoring of infrastructure and applications.

## When This Skill Activates

- Keywords: Prometheus, metrics, monitoring, alerting, scrape
- Editing `prometheus.yml`, `alerts.yml`
- Setting up monitoring infrastructure
- Implementing custom metrics

## Prometheus Configuration

### Basic Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'production'
    env: 'prod'

rule_files:
  - "alerts/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # FastAPI application
  - job_name: 'medsafe-api'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['api:8000']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        regex: '([^:]+):\d+'
        replacement: '${1}'

  # PostgreSQL
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Node exporter for system metrics
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # Docker containers
  - job_name: 'docker'
    static_configs:
      - targets: ['cadvisor:8080']
```

### FastAPI Integration

```python
# backend/app/middleware/prometheus.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import FastAPI, Request, Response
import time

# Define metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Active HTTP requests'
)

# Custom business metrics
DRUG_INTERACTIONS_CHECKED = Counter(
    'drug_interactions_checked_total',
    'Drug interactions checked',
    ['severity']
)

AGENT_EXECUTION_TIME = Histogram(
    'agent_execution_seconds',
    'Agent execution time',
    ['agent_name']
)

def setup_prometheus(app: FastAPI):
    """Add Prometheus middleware."""

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):
        ACTIVE_REQUESTS.inc()
        start_time = time.time()

        try:
            response = await call_next(request)

            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(time.time() - start_time)

            return response
        finally:
            ACTIVE_REQUESTS.dec()

    @app.get("/metrics")
    async def metrics():
        return Response(
            generate_latest(),
            media_type="text/plain"
        )
```

### Alert Rules

```yaml
# alerts/api.yml
groups:
  - name: api_alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m])) /
          sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: SlowResponses
        expr: |
          histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow API responses"
          description: "95th percentile latency is {{ $value }}s"

      - alert: HighMemoryUsage
        expr: |
          (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) /
          node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"

      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connections"
```

## Quick Reference

| Metric Type | Use Case | Example |
|-------------|----------|---------|
| Counter | Total count | Requests, errors |
| Gauge | Current value | Active connections |
| Histogram | Distribution | Latency |
| Summary | Quantiles | Response times |

**Remember**: Define meaningful labels, but don't create high cardinality!

---

## grafana-dashboards

# Grafana Dashboards

## Purpose

This skill provides patterns for creating effective Grafana dashboards for monitoring applications and infrastructure.

## When This Skill Activates

- Keywords: Grafana, dashboard, visualization, monitoring
- Creating monitoring dashboards
- Editing dashboard JSON
- Setting up observability

## Dashboard Structure

### API Performance Dashboard

```json
{
  "dashboard": {
    "title": "MedSafe API Performance",
    "tags": ["api", "performance"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Request Rate",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
          {
            "expr": "sum(rate(http_requests_total[5m])) by (endpoint)",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m])) * 100"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 1},
                {"color": "red", "value": 5}
              ]
            }
          }
        }
      },
      {
        "title": "P95 Latency",
        "type": "timeseries",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))",
            "legendFormat": "{{endpoint}}"
          }
        ],
        "fieldConfig": {
          "defaults": {"unit": "s"}
        }
      }
    ]
  }
}
```

### Agent Performance Dashboard

```json
{
  "panels": [
    {
      "title": "Agent Execution Time",
      "type": "timeseries",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(agent_execution_seconds_bucket[5m])) by (le, agent_name))",
          "legendFormat": "{{agent_name}}"
        }
      ]
    },
    {
      "title": "Drug Interactions by Severity",
      "type": "piechart",
      "targets": [
        {
          "expr": "sum(drug_interactions_checked_total) by (severity)"
        }
      ]
    },
    {
      "title": "HITL Queue Size",
      "type": "stat",
      "targets": [
        {
          "expr": "hitl_queue_size"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 5},
              {"color": "red", "value": 10}
            ]
          }
        }
      }
    }
  ]
}
```

### System Health Dashboard

```json
{
  "panels": [
    {
      "title": "CPU Usage",
      "type": "gauge",
      "targets": [
        {
          "expr": "100 - (avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "max": 100,
          "thresholds": {
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 70},
              {"color": "red", "value": 90}
            ]
          }
        }
      }
    },
    {
      "title": "Memory Usage",
      "type": "gauge",
      "targets": [
        {
          "expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100"
        }
      ]
    },
    {
      "title": "Disk Usage",
      "type": "bargauge",
      "targets": [
        {
          "expr": "100 - (node_filesystem_avail_bytes{mountpoint=\"/\"} / node_filesystem_size_bytes{mountpoint=\"/\"} * 100)"
        }
      ]
    },
    {
      "title": "Database Connections",
      "type": "timeseries",
      "targets": [
        {
          "expr": "pg_stat_activity_count",
          "legendFormat": "Active connections"
        }
      ]
    }
  ]
}
```

## Useful PromQL Queries

```promql
# Request rate per second
sum(rate(http_requests_total[5m]))

# Error percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100

# P95 latency
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Memory usage percentage
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) /
node_memory_MemTotal_bytes * 100

# CPU usage percentage
100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Top 5 slowest endpoints
topk(5, histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)))
```

## Dashboard Best Practices

1. **Row Organization**
   - Overview metrics at top
   - Detailed panels below
   - Group related panels

2. **Color Coding**
   - Green: Good
   - Yellow: Warning
   - Red: Critical

3. **Annotations**
   - Mark deployments
   - Track incidents
   - Correlate changes

## Quick Reference

| Panel Type | Use Case |
|------------|----------|
| Time series | Trends over time |
| Stat | Single important value |
| Gauge | Current vs max value |
| Table | Detailed data |
| Heatmap | Distribution patterns |
| Pie chart | Proportions |

**Remember**: A good dashboard tells a story. Start with the most important metrics!

---

# Criação de Documentos

---

## docx

---
name: docx
description: "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. When Claude needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"
license: Proprietary. LICENSE.txt has complete terms

---

## pptx

---
name: pptx
description: "Presentation creation, editing, and analysis. When Claude needs to work with presentations (.pptx files) for: (1) Creating new presentations, (2) Modifying or editing content, (3) Working with layouts, (4) Adding comments or speaker notes, or any other presentation tasks"
license: Proprietary. LICENSE.txt has complete terms

---

## xlsx

---
name: xlsx
description: "Comprehensive spreadsheet creation, editing, and analysis with support for formulas, formatting, data analysis, and visualization. When Claude needs to work with spreadsheets (.xlsx, .xlsm, .csv, .tsv, etc) for: (1) Creating new spreadsheets with formulas and formatting, (2) Reading or analyzing data, (3) Modify existing spreadsheets while preserving formulas, (4) Data analysis and visualization in spreadsheets, or (5) Recalculating formulas"
license: Proprietary. LICENSE.txt has complete terms

---

## pdf

---
name: pdf
description: Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms. When Claude needs to fill in a PDF form or programmatically process, generate, or analyze PDF documents at scale.
license: Proprietary. LICENSE.txt has complete terms

---

# Utilitários

---

## mcp-builder

---
name: mcp-builder
description: Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external services through well-designed tools. Use when building MCP servers to integrate external APIs or services, whether in Python (FastMCP) or Node/TypeScript (MCP SDK).
license: Complete terms in LICENSE.txt

---

## skill-creator

---
name: skill-creator
description: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Claude's capabilities with specialized knowledge, workflows, or tool integrations.
license: Complete terms in LICENSE.txt

---

# Workflows Avançados

---

## feature-dev-workflow

# Feature Development Workflow

## Purpose
Systematic 7-phase approach to building new features with proper exploration, design, and review phases, rather than jumping directly into coding.

## When This Skill Activates

**Automatically activates on:**
- Keywords: "build feature", "implement feature", "new feature", "feature development"
- Context: Large feature requests, complex implementations
- Intent: Structured approach to feature development

**Manual activation:**
"Use feature-dev-workflow to implement this feature"

## The 7 Phases

### Phase 1: Discovery
**Goal**: Clarify requirements and confirm understanding

**Activities:**
- Understand what needs building
- Identify stakeholders
- Define success criteria
- Confirm scope boundaries

**Deliverable**: Clear problem statement and requirements

**Example questions:**
- "What problem does this feature solve?"
- "Who are the users?"
- "What are the acceptance criteria?"
- "Are there any constraints?"

---

### Phase 2: Codebase Exploration
**Goal**: Understand existing implementations and identify key files

**Activities:**
- Launch 2-3 code-explorer agents in parallel
- Examine relevant existing implementations
- Identify key files to review
- Map out current architecture

**Agents used:** code-explorer (parallel execution)

**Deliverable**: Codebase understanding document with:
- Relevant existing features
- Key files and their purposes
- Current patterns and conventions
- Similar implementations for reference

**Example:**
```
Exploring authentication implementation:
- Agent #1: Examine auth middleware
- Agent #2: Review user session management
- Agent #3: Investigate token handling

Findings:
- Auth uses JWT in middleware/auth.py
- Sessions stored in Redis
- Token refresh in services/token_service.py
```

---

### Phase 3: Clarifying Questions
**Goal**: Identify and resolve underspecified aspects

**Activities:**
- Identify edge cases
- Clarify error handling requirements
- Define integration points
- Resolve ambiguities

**Deliverable**: Complete requirements with edge cases defined

**Example questions:**
- "How should the system handle network timeouts?"
- "What happens when user input is invalid?"
- "Should this integrate with existing notification system?"
- "What are the performance requirements?"

**User interaction:** Waits for your answers before proceeding

---

### Phase 4: Architecture Design
**Goal**: Design implementation approach with trade-offs

**Activities:**
- Launch 2-3 code-architect agents in parallel
- Generate different approaches
- Evaluate trade-offs
- Recommend best fit

**Agents used:** code-architect (parallel execution)

**Three typical approaches:**
1. **Minimal Changes** - Least invasive, quick, technical debt trade-off
2. **Clean Architecture** - Ideal design, more time, proper separation
3. **Pragmatic Balance** - Middle ground, balanced trade-offs

**Deliverable**: Architecture decision with reasoning

**Example:**
```
Notification System Design:

Approach 1 - Minimal (2-3 days):
+ Quick implementation
+ Uses existing email service
- Tightly coupled
- Hard to add channels later

Approach 2 - Clean Architecture (5-7 days):
+ Pluggable notification channels
+ Easy to test and maintain
+ Follows SOLID principles
- More upfront work
- Higher complexity

Approach 3 - Pragmatic (3-4 days): ⭐ RECOMMENDED
+ Abstraction for channels (email, SMS)
+ Reasonable testing
+ Can evolve to full architecture
- Some coupling remains
```

---

### Phase 5: Implementation
**Goal**: Build the feature following chosen architecture

**Activities:**
- Wait for explicit approval
- Follow chosen architecture
- Apply discovered codebase patterns
- Maintain consistency with existing code

**Requires:** User approval to proceed

**Deliverable**: Working implementation

**Best practices:**
- Follow existing patterns from Phase 2
- Address edge cases from Phase 3
- Implement according to Phase 4 design
- Write tests as you go

---

### Phase 6: Quality Review
**Goal**: Verify implementation quality and correctness

**Activities:**
- Launch 3 code-reviewer agents in parallel
- Review simplicity/elegance
- Check bugs/correctness
- Verify conventions compliance

**Agents used:** code-reviewer (parallel execution)

**Three review dimensions:**
1. **Simplicity/Elegance** - Is the code clear and maintainable?
2. **Bugs/Correctness** - Are there logic errors or edge cases missed?
3. **Conventions** - Does it follow project guidelines?

**Deliverable**: Quality report with findings

**User decision:** You decide which findings to address

**Example:**
```
Quality Review Results:

Simplicity Agent:
✓ Clear function names
⚠ Complex nested conditionals in validate_input() (MEDIUM)
✓ Good separation of concerns

Bug Hunter:
🚨 Potential null pointer in process_notification() (HIGH)
⚠ Race condition in concurrent access (MEDIUM)
✓ Edge cases handled

Conventions Checker:
✓ Follows backend-dev-guidelines
⚠ Missing docstrings on 2 functions (LOW)
✓ Proper error handling
```

---

### Phase 7: Summary
**Goal**: Document completed work and next steps

**Deliverable:** Comprehensive summary including:
- Key decisions made
- Modified files
- Architecture choices
- Remaining work (if any)
- Suggested next steps

**Example:**
```
Feature Implementation Summary: User Notifications

✅ Completed:
- Notification service with email and SMS channels
- Redis queue for async processing
- Notification preferences API
- Integration with existing user service

📁 Modified Files (12):
- services/notification_service.py (new)
- api/routes/notifications.py (new)
- models/notification.py (new)
- services/user_service.py (modified)
- ...

🏗 Architecture Decisions:
- Chose pragmatic approach (Phase 4)
- Used existing Redis for queuing
- Factory pattern for notification channels

📋 Next Steps:
1. Add web push notifications
2. Implement notification batching
3. Add notification history API
```

## Three Core Agents

### code-explorer
**Purpose**: Analyzes existing features

**Capabilities:**
- Trace execution paths
- Understand data flows
- Identify architecture patterns
- Provide implementation insights

**When used:** Phase 2 (Codebase Exploration)

---

### code-architect
**Purpose**: Designs feature architectures

**Capabilities:**
- Generate multiple approaches
- Analyze trade-offs
- Recommend best fit
- Create implementation blueprints

**When used:** Phase 4 (Architecture Design)

---

### code-reviewer
**Purpose**: Reviews code quality

**Capabilities:**
- Identify bugs
- Assess quality
- Check guideline compliance
- Use confidence-based filtering

**When used:** Phase 6 (Quality Review)

## Usage Patterns

### Full Workflow
```
User: "Implement user authentication with OAuth"

Phase 1: Confirms requirements (OAuth providers, session management, etc.)
Phase 2: Explores existing auth code (3 agents in parallel)
Phase 3: Asks edge case questions (token refresh, logout, etc.)
Phase 4: Presents 3 architecture options (minimal, clean, pragmatic)
Phase 5: Implements after approval
Phase 6: Reviews with 3 agents (simplicity, bugs, conventions)
Phase 7: Provides comprehensive summary
```

### Targeted Agent Usage
```
"Use code-explorer to understand the payment processing flow"
"Run code-architect to design the caching strategy"
"Have code-reviewer check this implementation"
```

## When to Use Full Workflow

Use all 7 phases for:
- ✅ New major features
- ✅ Complex integrations
- ✅ Architectural changes
- ✅ Unfamiliar codebases
- ✅ Production-critical features

Skip phases for:
- ❌ Bug fixes
- ❌ Simple additions
- ❌ Well-understood changes
- ❌ Trivial updates

## Benefits

### Comprehensive Planning
- Avoid jumping into code prematurely
- Understand existing patterns first
- Design before implementing

### Parallel Efficiency
- Multiple agents working simultaneously
- Faster exploration and review
- Comprehensive coverage

### Quality Assurance
- Built-in review process
- Multiple perspectives
- Confidence-based findings

### Documentation
- Clear decision trail
- Architecture reasoning preserved
- Easy handoff to team

## Integration with Existing Skills

**Synergies:**
- **backend-dev-guidelines** → Followed during implementation (Phase 5)
- **frontend-dev-guidelines** → Applied for frontend features
- **api-design-principles** → Used in architecture design (Phase 4)
- **database-verification** → Applied for schema changes
- **code-review-excellence** → Enhanced by quality review (Phase 6)
- **pr-review-agents** → Complements final review

## Customization

### Adjust Phases
Skip phases for simpler features:
```
Simple feature: Phases 1, 2, 5, 7 (skip 3, 4, 6)
Bug fix: Phases 2, 5 only
Exploration only: Phases 1, 2, 3
```

### Agent Configuration
- Add more agents for larger codebases
- Reduce agents for smaller projects
- Customize agent focus areas

## Examples

### Example 1: API Endpoint Feature
```
Feature: "Add pagination to users list endpoint"

Phase 1: Confirm page size, max limits, offset vs cursor
Phase 2: Explore existing pagination in other endpoints
Phase 3: Ask about default page size, error handling
Phase 4: Design - reuse existing pagination helper
Phase 5: Implement with query parameters
Phase 6: Review for consistency and edge cases
Phase 7: Summary of changes and pagination pattern used
```

### Example 2: Frontend Component
```
Feature: "Build a dashboard with real-time updates"

Phase 1: Clarify data sources, update frequency, UI layout
Phase 2: Explore existing real-time components, WebSocket setup
Phase 3: Ask about fallback behavior, error states
Phase 4: Design WebSocket vs SSE vs polling approach
Phase 5: Implement with chosen approach
Phase 6: Review component structure, hook usage, performance
Phase 7: Document component API and usage patterns
```

## Meta

**Type**: Domain
**Priority**: High
**Enforcement**: Suggest
**Author**: Anthropic (adapted from official plugin)
**Version**: 1.0.0
**Phases**: 7
**Agents**: 3 core agents

## Quick Reference Card

```
Phase 1: Discovery ────────────► Clear requirements
Phase 2: Exploration ──────────► Codebase understanding (3 agents ∥)
Phase 3: Clarifying Qs ────────► Complete requirements
Phase 4: Architecture ─────────► Design decision (3 approaches ∥)
Phase 5: Implementation ───────► Working code
Phase 6: Quality Review ───────► Quality report (3 agents ∥)
Phase 7: Summary ──────────────► Documentation

∥ = Parallel execution
```

---

## code-review-parallel

# Code Review Parallel

## Purpose
Automates pull request review by launching multiple specialized agents in parallel with confidence-based scoring to filter false positives.

## When This Skill Activates

**Automatically activates on:**
- Keywords: "code review", "automated review", "review PR", "parallel review"
- File patterns: Pull request workflows, review automation
- Intent: Running automated code reviews with multiple agents

**Manual activation:**
"Run code-review-parallel on this PR"

## What This Skill Provides

### Multi-Agent Review System

Launches 4 parallel specialized agents for comprehensive review:

1. **CLAUDE.md Compliance Auditors (Agents #1 & #2)**
   - Verify adherence to project guidelines
   - Check coding standards and conventions
   - Validate architectural patterns

2. **Bug Scanner (Agent #3)**
   - Scan for obvious bugs in changes
   - Identify logic errors
   - Detect potential runtime issues

3. **Context Analyzer (Agent #4)**
   - Analyze git blame/history
   - Identify context-based issues
   - Review historical patterns

### Confidence-Based Filtering

**Scoring Scale (0-100):**
- **0**: Not confident, false positive
- **25**: Somewhat confident
- **50**: Moderately confident
- **75**: Highly confident
- **100**: Absolutely certain

**Default threshold: 80** (only high-confidence issues posted)

### Review Process Flow

1. Validate PR eligibility (skip closed, draft, trivial, or already-reviewed)
2. Gather CLAUDE.md guideline files
3. Summarize pull request changes
4. Launch 4 parallel review agents
5. Score each issue 0-100 for confidence
6. Filter issues below threshold
7. Post review with high-confidence issues only

## Best Practices

### When to Use
- Before merging significant pull requests
- For code quality gates in CI/CD
- When reviewing complex changes
- To catch issues human reviewers might miss

### Customization Options

**Adjust Confidence Threshold:**
Modify threshold based on team preference:
- **90-100**: Only absolute certainties (fewer false positives)
- **70-80**: Balanced approach (recommended)
- **50-70**: More warnings (more false positives)

**Add Specialized Agents:**
- Security analysis agent
- Performance evaluation agent
- Accessibility checking agent
- Documentation quality agent

## Integration Examples

### Standard PR Workflow
```
1. Create PR
2. Run /code-review (or automated trigger)
3. Review feedback
4. Fix high-confidence issues
5. Merge
```

### CI/CD Integration
```yaml
# Trigger on PR creation/update
# Auto-comment with findings
# Skip if already reviewed
```

### Manual Usage
```
"Run parallel code review on PR #123"
"Analyze this pull request with confidence scoring"
"Review my changes with CLAUDE.md compliance check"
```

## Key Features

✅ **Multiple Independent Agents** - Comprehensive coverage
✅ **Confidence-Based Scoring** - Reduces false positives
✅ **CLAUDE.md Integration** - Project-specific guidelines
✅ **Historical Context** - Git blame analysis
✅ **Automatic Skipping** - Ineligible PRs ignored
✅ **Direct Code Links** - Full SHA and line ranges

## Requirements

- Git repository with GitHub integration
- GitHub CLI (`gh`) installed and authenticated
- CLAUDE.md files (optional but recommended)

## Examples

### Example 1: Standard Review
```
User: "Review PR #456 with parallel agents"

Claude:
1. Validates PR is open and reviewable
2. Gathers CLAUDE.md guidelines
3. Launches 4 agents in parallel
4. Agent #1 finds 3 style violations (confidence: 95)
5. Agent #3 finds 1 potential null pointer (confidence: 85)
6. Agent #4 finds historical pattern issue (confidence: 92)
7. Posts review with 3 high-confidence findings
```

### Example 2: Custom Threshold
```
User: "Review this PR with 90% confidence threshold"

Claude: Adjusts threshold and runs review with stricter filtering
```

### Example 3: Skip Logic
```
User: "Review PR #789"

Claude: "PR #789 is already reviewed, skipping to avoid duplicate comments"
```

## Comparison with Traditional Review

| Aspect | Traditional | Code Review Parallel |
|--------|-------------|---------------------|
| Coverage | Single reviewer perspective | 4 specialized perspectives |
| Speed | Hours to days | Minutes |
| Consistency | Varies by reviewer | Consistent patterns |
| False Positives | Depends on reviewer | Filtered by confidence score |
| CLAUDE.md | Manual checking | Automatic verification |
| Historical Context | Manual git blame | Automatic analysis |

## Advanced Patterns

### Security-Focused Review
Add security agent for:
- SQL injection patterns
- XSS vulnerabilities
- Authentication/authorization issues
- Sensitive data exposure

### Performance Review
Add performance agent for:
- N+1 query detection
- Memory leak patterns
- Inefficient algorithms
- Resource management

### Accessibility Review
Add a11y agent for:
- ARIA label compliance
- Keyboard navigation
- Screen reader compatibility
- Color contrast

## Meta

**Type**: Utility
**Priority**: High
**Enforcement**: Suggest
**Author**: Anthropic (adapted from official plugin)
**Version**: 1.0.0

---

## pr-review-agents

# PR Review Agents

## Purpose
Comprehensive collection of six specialized agents for thorough pull request review, covering documentation, tests, error handling, types, code quality, and simplification.

## When This Skill Activates

**Automatically activates on:**
- Keywords: "PR review", "test coverage", "error handling", "type design", "simplify code"
- Context: Code review requests, before commits, before PRs
- Intent: Detailed code quality analysis

**Manual activation:**
"Use pr-review-agents to analyze this code"

## The Six Specialized Agents

### 1. Comment-Analyzer
**Focus**: Documentation accuracy and maintainability

**What it checks:**
- Comment correctness against actual code
- Outdated or misleading documentation
- Comment-related technical debt
- Documentation gaps

**Trigger examples:**
- "Check if the comments are accurate"
- "Review the documentation I added"
- "Are these comments up to date?"

**When to use:** Before committing changes with new/updated documentation

---

### 2. PR-Test-Analyzer
**Focus**: Test coverage quality

**What it checks:**
- Behavioral versus line coverage
- Critical testing gaps
- Test resilience
- Edge case handling
- Test maintainability

**Trigger examples:**
- "Check if the tests are thorough"
- "Are there any critical test gaps?"
- "Review test coverage"

**When to use:** Before creating PR, after adding new features

---

### 3. Silent-Failure-Hunter
**Focus**: Error handling robustness

**What it checks:**
- Silent failures in catch blocks
- Inadequate error handling patterns
- Missing error logging
- Swallowed exceptions
- Error propagation issues

**Trigger examples:**
- "Review the error handling"
- "Check for silent failures"
- "Are errors properly logged?"

**When to use:** Before committing, for production-critical code

---

### 4. Type-Design-Analyzer
**Focus**: Type system quality

**Evaluation dimensions (1-10 scale):**
1. **Encapsulation** - Hides implementation details
2. **Invariant Expression** - Enforces business rules
3. **Usefulness** - Provides meaningful abstraction
4. **Enforcement** - Prevents invalid states

**What it checks:**
- Type safety and design integrity
- Proper use of type systems
- Type-level constraints
- Invalid state prevention

**Trigger examples:**
- "Review the UserAccount type design"
- "Check if this type has strong invariants"
- "Evaluate type safety"

**When to use:** When designing core domain types, before major refactors

---

### 5. Code-Reviewer
**Focus**: General code quality and compliance

**What it checks:**
- Project guideline adherence (CLAUDE.md)
- Bug detection
- Quality issues
- Style violations
- Best practice compliance

**Trigger examples:**
- "Review my recent changes"
- "Review this code before I commit"
- "Check for bugs and quality issues"

**When to use:** Before committing, as general-purpose reviewer

---

### 6. Code-Simplifier
**Focus**: Code clarity and maintainability

**What it checks:**
- Unnecessary complexity
- Deep nesting
- Redundant abstractions
- Over-engineering
- Code clarity opportunities

**What it provides:**
- Simplification suggestions
- Preserved functionality guarantees
- Clarity improvements

**Trigger examples:**
- "Simplify this code"
- "Make this clearer"
- "Is this over-engineered?"

**When to use:** After code review, for polish before merge

## Recommended Workflow

### Before Committing
```
1. Run silent-failure-hunter (error handling)
2. Run code-reviewer (general quality)
3. Fix critical issues
4. Commit
```

### Before Creating PR
```
1. Run pr-test-analyzer (test coverage)
2. Run comment-analyzer (documentation)
3. Run type-design-analyzer (type quality)
4. Run code-reviewer (final check)
5. Address findings
6. Create PR
```

### After Code Review
```
1. Run code-simplifier (polish)
2. Apply clarity improvements
3. Merge
```

### Full Quality Gate
```
1. comment-analyzer → Documentation
2. pr-test-analyzer → Tests
3. silent-failure-hunter → Error handling
4. type-design-analyzer → Type design
5. code-reviewer → General quality
6. code-simplifier → Final polish
```

## Agent Output Format

All agents provide:
- **Structured, actionable output**
- **Specific file and line references**
- **Suggestions for improvement**
- **Severity prioritization** (critical, high, medium, low)

## Best Practices

### Selective Usage
Don't run all agents every time. Choose based on:
- **Quick commit:** code-reviewer only
- **Feature complete:** all agents except simplifier
- **Pre-merge polish:** code-simplifier
- **Production-critical:** silent-failure-hunter + code-reviewer

### Interpretation
- **Critical severity:** Must fix before merge
- **High severity:** Should fix before merge
- **Medium severity:** Consider fixing
- **Low severity:** Nice to have

### Iteration
Run agents iteratively:
1. First pass: Identify major issues
2. Fix and commit
3. Second pass: Polish and improve
4. Final commit

## Agent Synergy

Agents complement each other:
- **comment-analyzer** finds docs issues → **code-simplifier** suggests clearer code
- **pr-test-analyzer** finds test gaps → **code-reviewer** validates fixes
- **type-design-analyzer** improves types → **silent-failure-hunter** validates error handling
- **code-reviewer** finds bugs → **code-simplifier** improves readability

## Examples

### Example 1: Test Coverage Review
```
User: "Check if my tests are thorough"

PR-Test-Analyzer:
✓ Line coverage: 87% (good)
⚠ Behavioral coverage gaps:
  - Error scenarios not tested (HIGH)
  - Edge case: empty array handling (MEDIUM)
  - Concurrent modification scenario missing (MEDIUM)

Suggestions:
1. Add test for API timeout scenario
2. Test empty/null input handling
3. Add concurrent access test
```

### Example 2: Error Handling Review
```
User: "Review error handling in UserService"

Silent-Failure-Hunter:
🚨 Critical issues found:
1. services/user.py:42 - Empty catch block swallows exception
2. services/user.py:67 - Error logged but not re-raised
3. services/user.py:89 - Generic exception catch too broad

Recommendations:
- Add specific error types
- Log with context before re-raising
- Handle specific exceptions only
```

### Example 3: Type Design Review
```
User: "Review the UserAccount type design"

Type-Design-Analyzer:
Scoring (1-10):
- Encapsulation: 8/10 (good)
- Invariant Expression: 5/10 (weak) ⚠
- Usefulness: 7/10 (acceptable)
- Enforcement: 6/10 (moderate) ⚠

Issues:
1. Email validation not enforced at type level
2. Age can be negative (invariant violation)
3. Username allows empty strings

Suggestions:
- Use branded types for Email
- Add Age constraint type (positive integer)
- Use NonEmptyString for Username
```

## Integration with Existing Workflow

Complements existing skills:
- **backend-dev-guidelines** → code-reviewer validates patterns
- **frontend-dev-guidelines** → comment-analyzer checks React docs
- **python-testing-patterns** → pr-test-analyzer validates pytest usage
- **database-verification** → type-design-analyzer checks model types
- **code-review-excellence** → All agents enhance review quality

## Meta

**Type**: Utility
**Priority**: High
**Enforcement**: Suggest
**Author**: Anthropic (adapted from official plugin)
**Version**: 1.0.0
**Agents**: 6 specialized reviewers

## Quick Reference

| Agent | When to Use | Primary Focus |
|-------|-------------|---------------|
| comment-analyzer | Documentation changes | Doc accuracy |
| pr-test-analyzer | Feature complete | Test coverage |
| silent-failure-hunter | Before commit | Error handling |
| type-design-analyzer | Type changes | Type safety |
| code-reviewer | Always | General quality |
| code-simplifier | Before merge | Code clarity |

---

# Integração com Claude-Mem

---

## claude-mem-integration

# Claude-Mem Integration

## Purpose

This skill provides automatic integration with the **claude-mem** plugin, a persistent memory system that captures tool usage, compresses observations with AI, and injects relevant context into future sessions.

## When This Skill Activates

This skill auto-activates when:

1. **Memory-related keywords** are detected:
   - "remember", "recall", "previous session", "last time", "what did we do"
   - "history", "context", "past work", "earlier", "before"
   - "memory", "persistent", "session context"

2. **Session start** - Claude-mem automatically injects relevant context from past sessions

3. **Tool usage tracking** - All tool outputs are automatically observed and compressed

4. **User asks about past work**:
   - "What bugs did we fix?"
   - "What features did we implement?"
   - "Show me what we worked on"

## Key Features

### Automatic Session Memory
- Context from previous sessions automatically appears at session start
- Tool usage is tracked and compressed using AI (10:1 to 100:1 compression ratio)
- Semantic search across all past sessions

### Privacy Control
Use `<private>` tags to exclude sensitive content from storage:
```
<private>
API_KEY=sk-secret-key-here
</private>
```

### Memory Search
Query your project history with natural language:
- "What authentication changes were made last week?"
- "Find all database schema modifications"
- "Show me the API endpoints we created"

### Web Viewer UI
Real-time memory stream available at: **http://localhost:37777**

## Commands & Usage

### Check Worker Status
```bash
cd ~/.claude/plugins/marketplaces/claude-mem && npm run worker:status
```

### Start Worker Service
```bash
cd ~/.claude/plugins/marketplaces/claude-mem && npm run worker:start
```

### View Worker Logs
```bash
cd ~/.claude/plugins/marketplaces/claude-mem && npm run worker:logs
```

### Restart Worker
```bash
cd ~/.claude/plugins/marketplaces/claude-mem && npm run worker:restart
```

## Configuration

Settings are stored in `~/.claude-mem/settings.json`:

```json
{
  "CLAUDE_MEM_MODEL": "claude-sonnet-4-5",
  "CLAUDE_MEM_CONTEXT_OBSERVATIONS": 10,
  "CLAUDE_MEM_WORKER_PORT": 37777,
  "CLAUDE_MEM_LOG_LEVEL": "INFO"
}
```

### Key Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `CLAUDE_MEM_MODEL` | Model for observations/summaries | claude-sonnet-4-5 |
| `CLAUDE_MEM_CONTEXT_OBSERVATIONS` | Observations injected at session start | 10 |
| `CLAUDE_MEM_WORKER_PORT` | Worker service port | 37777 |
| `CLAUDE_MEM_LOG_LEVEL` | Log verbosity (DEBUG, INFO, WARN, ERROR, SILENT) | INFO |

## File Locations

| Location | Purpose |
|----------|---------|
| `~/.claude/plugins/marketplaces/claude-mem/` | Installed plugin |
| `~/.claude-mem/claude-mem.db` | SQLite database |
| `~/.claude-mem/chroma/` | Vector embeddings |
| `~/.claude-mem/settings.json` | Configuration |
| `~/.claude-mem/logs/` | Worker logs |

## Architecture

Claude-mem operates through 5 lifecycle hooks:

1. **SessionStart** - Injects relevant context from past sessions
2. **UserPromptSubmit** - Tracks user requests
3. **PostToolUse** - Captures tool outputs and compresses them
4. **Summary** - Generates session summaries
5. **SessionEnd** - Finalizes session data

## Best Practices

### DO:
- Let claude-mem run automatically in the background
- Use `<private>` tags for sensitive information
- Query past sessions when you need context about previous work
- Check the web viewer at http://localhost:37777 for real-time insights

### DON'T:
- Store API keys or credentials without `<private>` tags
- Disable the worker service during active development
- Delete the database without backing up important observations

## Troubleshooting

### Worker not starting?
```bash
# Check if Bun is installed
bun --version

# If not, install it
curl -fsSL https://bun.sh/install | bash

# Then restart the worker
cd ~/.claude/plugins/marketplaces/claude-mem && npm run worker:restart
```

### Memory not being injected?
1. Verify worker is running: `npm run worker:status`
2. Check logs: `npm run worker:logs`
3. Ensure `CLAUDE_MEM_CONTEXT_OBSERVATIONS` > 0

### High memory usage?
- Reduce `CLAUDE_MEM_CONTEXT_OBSERVATIONS` in settings
- Clear old data: `rm ~/.claude-mem/claude-mem.db` (backup first!)

## Integration with Other Skills

Claude-mem works seamlessly with all other skills. It automatically captures:
- Code changes made during sessions
- Debugging sessions and solutions
- API design decisions
- Test implementations
- Performance optimizations

This creates a persistent knowledge base of your development history.

## Resources

- **Documentation**: https://docs.claude-mem.ai
- **GitHub**: https://github.com/thedotmack/claude-mem
- **Web Viewer**: http://localhost:37777
- **Issues**: https://github.com/thedotmack/claude-mem/issues

---

# Outras Skills

---

## algorithmic-art

---
name: algorithmic-art
description: Creating algorithmic art using p5.js with seeded randomness and interactive parameter exploration. Use this when users request creating art using code, generative art, algorithmic art, flow fields, or particle systems. Create original algorithmic art rather than copying existing artists' work to avoid copyright violations.
license: Complete terms in LICENSE.txt

---

## artifacts-builder

---
name: artifacts-builder
description: Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies (React, Tailwind CSS, shadcn/ui). Use for complex artifacts requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX artifacts.
license: Complete terms in LICENSE.txt

---

## brand-guidelines

---
name: brand-guidelines
description: Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic's look-and-feel. Use it when brand colors or style guidelines, visual formatting, or company design standards apply.
license: Complete terms in LICENSE.txt

---

## canvas-design

---
name: canvas-design
description: Create beautiful visual art in .png and .pdf documents using design philosophy. You should use this skill when the user asks to create a poster, piece of art, design, or other static piece. Create original visual designs, never copying existing artists' work to avoid copyright violations.
license: Complete terms in LICENSE.txt

---

## internal-comms

---
name: internal-comms
description: A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. Claude should use this skill whenever asked to write some sort of internal communications (status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, project updates, etc.).
license: Complete terms in LICENSE.txt

---

## product-self-knowledge

---
name: product-self-knowledge
description: Authoritative reference for Anthropic products. Use when users ask about product capabilities, access, installation, pricing, limits, or features. Provides source-backed answers to prevent hallucinations about Claude.ai, Claude Code, and Claude API.

---

## slack-gif-creator

---
name: slack-gif-creator
description: Knowledge and utilities for creating animated GIFs optimized for Slack. Provides constraints, validation tools, and animation concepts. Use when users request animated GIFs for Slack like "make me a GIF of X doing Y for Slack."
license: Complete terms in LICENSE.txt

---

## theme-factory

---
name: theme-factory
description: Toolkit for styling artifacts with a theme. These artifacts can be slides, docs, reportings, HTML landing pages, etc. There are 10 pre-set themes with colors/fonts that you can apply to any artifact that has been creating, or can generate a new theme on-the-fly.
license: Complete terms in LICENSE.txt

---

# Referência Rápida

## Categorias por Tipo

| Tipo | Quantidade | Exemplos |
|------|------------|----------|
| **domain** | 9 | backend, frontend, api-design, testing |
| **utility** | 11 | github-actions, docx, pptx, mcp-builder |
| **guardrail** | 1 | database-verification |
| **meta** | 2 | skill-creator, ultrathink |

## Categorias por Prioridade

| Prioridade | Quantidade | Propósito |
|------------|------------|-----------|
| **CRITICAL** | 1 | Pode bloquear operações inseguras |
| **HIGH** | 5 | Workflows de desenvolvimento principais |
| **MEDIUM** | 11 | Importantes mas não críticos |
| **LOW** | 8 | Utilitários e helpers |

## Categorias por Enforcement

| Enforcement | Quantidade | Comportamento |
|-------------|------------|---------------|
| **block** | 1 | Pode prevenir edições (database-verification) |
| **suggest** | 24 | Fornece orientação e padrões |

---

## Skills Mais Úteis

Baseado na frequência de uso:

1. **backend-dev-guidelines** - Usado constantemente para trabalho backend
2. **frontend-dev-guidelines** - Usado constantemente para trabalho frontend
3. **database-verification** - Rede de segurança crítica
4. **api-design-principles** - Essencial para desenvolvimento de API
5. **debugging-strategies** - Útil quando estiver travado
6. **python-testing-patterns** - Importante para qualidade
7. **ultrathink** - Para soluções de alta qualidade

---

## Estrutura de uma Skill

Cada skill deve seguir esta estrutura:

```
skill-name/
├── SKILL.md                     # Arquivo principal da skill (obrigatório)
└── resources/                   # Referências detalhadas opcionais
    ├── advanced.md
    ├── examples.md
    └── troubleshooting.md
```

**SKILL.md deve ser**:
- Menos de 500 linhas (manter focado)
- Rico em exemplos (amostras de código)
- Baseado em comparações (exemplos BOM vs RUIM)
- Acionável (checklists e referências rápidas)

---

## Arquivos Relacionados

- **Configuração**: `~/.claude/skill-rules.json`
- **Config Global**: `~/.claude/CLAUDE.md`
- **Hooks**: `~/.claude/hooks/`

---

## Dicas

1. **Seja Específico**: "seguindo backend-dev-guidelines" é melhor do que apenas mencionar "backend"
2. **Combine Skills**: "Criar endpoint de API seguindo backend-dev-guidelines e api-design-principles"
3. **Revise Skills**: Periodicamente leia os arquivos SKILL.md para aprender padrões
4. **Personalize**: Não hesite em editar skills para corresponder às convenções da sua equipe
5. **Compartilhe**: Se você criar uma ótima skill, compartilhe com a comunidade!

---

**Total de Linhas de Documentação**: 5,140+
**Skills Documentadas com Conteúdo Completo**: 12
**Skills com Descrição Resumida**: 13 (plugins de terceiros)
**Pronto para Usar**: Sim!

Comece a codificar e veja as skills ativarem automaticamente!

---

**Última Atualização**: 29/12/2025
**Versão**: 2.0.0 (Documentação Completa)
