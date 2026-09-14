import App from '../App.tsx';
import Data from '../features/data/Data.tsx';
import Diagnostics from '../features/data/diagnostics/Diagnostics.tsx';
import Prescriptions from '../features/data/prescriptions/Prescriptions.tsx';
import Certificates from '../features/data/certificates/Certificates.tsx';
import OtherMedications from '../features/data/otherMedications/OtherMedications.tsx';
import Recipients from '../features/Recipients/Recipients.tsx';
import Profile from '../features/profile/Profile.tsx';
import { createBrowserRouter } from 'react-router-dom';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        path: 'data',
        element: <Data />,
        children: [
          {
            index: true,
            element: <Diagnostics />,
          },
          {
            path: 'prescriptions',
            element: <Prescriptions />,
          },
          {
            path: 'certificates',
            element: <Certificates />,
          },
          {
            path: 'other_medications',
            element: <OtherMedications />,
          },
        ],
      },
      {
        path: 'profile',
        element: <Profile />,
      },
      {
        path: 'recipients',
        element: <Recipients />,
      },
    ],
  },
]);
