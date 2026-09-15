import App from '../App.tsx';
import Documents from '../features/documents/Documents.tsx';
import Diagnostics from '../features/documents/diagnostics/Diagnostics.tsx';
import Prescriptions from '../features/documents/prescriptions/Prescriptions.tsx';
import Certificates from '../features/documents/certificates/Certificates.tsx';
import OtherMedications from '../features/documents/otherMedications/OtherMedications.tsx';
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
        element: <Documents />,
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
