import { useNavigate } from 'react-router-dom';
import { useDatasetStore } from '../../store/datasetStore';

/** Leaves the recipient's vault and lands back on the user's own records. */
export function useSwitchToSelf() {
  const switchToSelf = useDatasetStore((state) => state.switchToSelf);
  const navigate = useNavigate();

  return () => {
    void switchToSelf();
    navigate('/documents');
  };
}
