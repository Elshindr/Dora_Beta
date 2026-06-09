import { render, screen, waitFor } from '@testing-library/react';
import App from './App';

global.fetch = jest.fn();

jest.mock('react-leaflet', () => ({
  MapContainer: ({ children }) => <div>{children}</div>,
  TileLayer: () => <div />,
  Marker: ({ children }) => <div>{children}</div>,
  Popup: ({ children }) => <div>{children}</div>,
}));

jest.mock('@changey/react-leaflet-markercluster', () => ({
  __esModule: true,
  default: ({ children }) => <div>{children}</div>,
}));

jest.mock('./routing', () => () => <div />);

describe('App', () => {

  beforeEach(() => {
    fetch.mockClear();
  });

  test('charge les catégories', async () => {

    fetch.mockResolvedValueOnce({
      json: async () => [
        { idCat: 1, name: 'Restaurant' },
        { idCat: 2, name: 'Musée' },
      ]
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Restaurant')).toBeInTheDocument();
    });

    expect(screen.getByText('Musée')).toBeInTheDocument();
  });

});