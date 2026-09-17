import mockDataService from './mockDatasetService.ts';
import datasetService from './datasetService.ts';

export const datasetApi =
  import.meta.env.MODE === 'mock' ? mockDataService : datasetService;
