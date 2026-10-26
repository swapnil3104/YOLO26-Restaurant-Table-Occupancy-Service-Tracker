import React from 'react';
import { 
  SurveillancePage, 
  SurveillancePageProps, 
  SurveillancePrimaryView 
} from './SurveillancePage';
import { GridLayoutMode } from '../components/surveillance/CameraGrid';

export type { SurveillancePrimaryView };
export type SubGridLayout = GridLayoutMode;
export type SurveillanceVisionPageProps = SurveillancePageProps;

export const SurveillanceVisionPage: React.FC<SurveillanceVisionPageProps> = (props) => {
  return <SurveillancePage {...props} />;
};

export default SurveillanceVisionPage;
