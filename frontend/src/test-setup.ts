import '@testing-library/jest-dom/vitest';
import { configure } from '@testing-library/react';

// Same assertions, longer polling budget for slow CI runners (default 1 s).
configure({ asyncUtilTimeout: 5000 });
