import mockDataService from './mockDatasetService';
import datasetService from './datasetService';
import mockCaregiverService from './mockCaregiverService';
import caregiverService from './caregiverService';

export const datasetApi =
  import.meta.env.MODE === 'mock' ? mockDataService : datasetService;

export const caregiverApi =
  import.meta.env.MODE === 'mock' ? mockCaregiverService : caregiverService;
