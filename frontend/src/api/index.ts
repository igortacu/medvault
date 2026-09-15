import { mockMedVaultService } from './mockScheduleService';
import { medVaultService } from './scheduleService';

export const datasetApi =
  import.meta.env.MODE === 'mock' ? mockMedVaultService : medVaultService;
