import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import App from './App';

//Mock cartographique
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

// Données mock
const mockCategories = [
  { idCat: 1, name: 'Restaurant', idFsq: 'fsq1' },
  { idCat: 2, name: 'Musée', idFsq: 'fsq2' },
];

const mockPois = [
  { idPoi: 10, namePoi: 'Tour Eiffel', latitudePoi: 48.858, longitudePoi: 2.294, nameCat: 'Monument', address: 'Paris', note: 5, idCat: 3 },
];

// Mock global
beforeEach(() => {
  global.fetch = jest.fn((url) => {
    if (url.includes('/api/cats'))
      return Promise.resolve({ json: () => Promise.resolve(mockCategories) });
    if (url.includes('/api/poisbycats/'))
      return Promise.resolve({ json: () => Promise.resolve(mockPois) });
    if (url.includes('/api/avisbypoi/'))
      return Promise.resolve({ json: () => Promise.resolve([]) });
    if (url.includes('/api/recommend_from_selection'))
      return Promise.resolve({ json: () => Promise.resolve([{ idPoi: 20 }]) });
    if (url.includes('/api/poi_by_ids'))
      return Promise.resolve({ json: () => Promise.resolve([]) });
    if (url.includes('/api/optimize-itinerary/'))
      return Promise.resolve({ json: () => Promise.resolve({
        'Jour 1': { pois: [{ id: 10, name: 'Tour Eiffel', lat: 48.858, lon: 2.294 }], distance_km: 2.5, extra_day: false }
      })});
    return Promise.resolve({ json: () => Promise.resolve([]) });
  });
});

afterEach(() => jest.resetAllMocks());




// =========================================================
// ==================== CATEGORIES =========================
// =========================================================

test('charge les catégories au démarrage', async () => {
  render(<App />);
  await waitFor(() => {
    expect(screen.getByText('Restaurant')).toBeInTheDocument();
    expect(screen.getByText('Musée')).toBeInTheDocument();
  });
});


test('filtre les catégories', async () => {
  render(<App />);

  await waitFor(() => screen.getByText('Restaurant'));

  const input = screen.getByPlaceholderText(/rechercher/i);
  await userEvent.type(input, 'mus');

  expect(screen.getByText('Musée')).toBeInTheDocument();
  expect(screen.queryByText('Restaurant')).not.toBeInTheDocument();
});





// =========================================================
// ======================= DATES ===========================
// =========================================================

test('affiche une erreur si les dates sont absentes', async () => {
  render(<App />);
  await waitFor(() => screen.getByText('Restaurant'));

  const btn = screen.getByText("Calculer l'itinéraire");
  fireEvent.click(btn, { bubbles: true, cancelable: true });

  const dateInputs = document.querySelectorAll('input[type="date"]');
  fireEvent.change(dateInputs[0], { target: { value: '2025-12-10' } });
});


test('affiche une erreur si date fin avant date début', async () => {
  render(<App />);

  await waitFor(() => screen.getByText('Restaurant'));

  const dateInputs = document.querySelectorAll('input[type="date"]');
  fireEvent.change(dateInputs[0], { target: { value: '2025-12-10' } });
  fireEvent.change(dateInputs[1], { target: { value: '2025-12-01' } });

  fireEvent.click(screen.getByText("Calculer l'itinéraire"));

  await waitFor(() => {
    expect(screen.getByText(/date de fin doit être après/i)).toBeInTheDocument();
  });
});