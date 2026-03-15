jest.mock('./pages/Login', () => () => <div>Login page</div>);
jest.mock('./pages/Register', () => () => <div>Register page</div>);
jest.mock('./pages/Profile', () => () => <div>Profile page</div>);
jest.mock('./pages/Championship', () => () => <div>Championship page</div>);
jest.mock('./pages/Knowledge', () => () => <div>Knowledge page</div>);
jest.mock('./pages/KnowledgeArticle', () => () => <div>Knowledge article page</div>);
jest.mock('./pages/Education', () => () => <div>Education page</div>);
jest.mock('./pages/EducationTask', () => () => <div>Education task page</div>);
jest.mock('./pages/Home', () => () => <div>Home page</div>);
jest.mock('./pages/Landing', () => () => <div>Landing page mock</div>);
jest.mock('./pages/LandingLegal', () => () => <div>Landing legal mock</div>);
jest.mock('./pages/Rating', () => () => <div>Rating page</div>);
jest.mock('./pages/Admin', () => () => <div>Admin page</div>);
jest.mock('./components/Layout', () => () => <div>App layout</div>);
jest.mock('./components/MobileBlock', () => () => <div>Mobile block</div>);
jest.mock('./components/LoadingState', () => ({
  FullScreenLoader: ({ label }) => <div>{label}</div>,
}));

jest.mock('react-router-dom', () => {
  const React = require('react');

  const getPathFromHash = () => {
    const rawHash = String(globalThis.location?.hash || '');
    const withoutHash = rawHash.startsWith('#') ? rawHash.slice(1) : rawHash;
    const [path] = withoutHash.split('?');
    return path || '/';
  };

  return {
    HashRouter: ({ children }) => <>{children}</>,
    Routes: ({ children }) => {
      const currentPath = getPathFromHash();
      const routes = React.Children.toArray(children);
      const matchingRoute = routes.find((route) => route?.props?.path === currentPath)
        || routes.find((route) => route?.props?.path === '*');
      return matchingRoute?.props?.element || null;
    },
    Route: () => null,
    Navigate: ({ to }) => <div>{`Navigate:${to}`}</div>,
    useLocation: () => ({ pathname: getPathFromHash(), search: '', hash: globalThis.location?.hash || '' }),
  };
}, { virtual: true });

const mockBootstrapAuth = jest.fn(() => Promise.resolve({ reason: '' }));
const mockIsAuthenticated = jest.fn(() => false);
const mockWarmup = jest.fn();

jest.mock('./services/api', () => ({
  authAPI: {
    warmup: () => mockWarmup(),
    isAuthenticated: () => mockIsAuthenticated(),
    bootstrapAuth: () => mockBootstrapAuth(),
  },
}));

import { render, screen } from '@testing-library/react';

import App from './App';

function installMatchMedia(matches) {
  window.matchMedia = jest.fn().mockImplementation(() => ({
    matches,
    media: '(max-width: 1023px)',
    onchange: null,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    addListener: jest.fn(),
    removeListener: jest.fn(),
    dispatchEvent: jest.fn(),
  }));
}

describe('App landing routing', () => {
  beforeEach(() => {
    mockBootstrapAuth.mockClear();
    mockWarmup.mockClear();
    mockIsAuthenticated.mockClear();
    window.localStorage.clear();
  });

  it('renders landing on mobile hash route without MobileBlock', async () => {
    window.innerWidth = 390;
    window.location.hash = '#/landing';
    installMatchMedia(true);

    render(<App />);

    expect(await screen.findByText('Landing page mock')).toBeInTheDocument();
    expect(screen.queryByText('Mobile block')).not.toBeInTheDocument();
  });

  it('keeps MobileBlock for internal routes on mobile', () => {
    window.innerWidth = 390;
    window.location.hash = '#/home';
    installMatchMedia(true);

    render(<App />);

    expect(screen.getByText('Mobile block')).toBeInTheDocument();
  });
});
