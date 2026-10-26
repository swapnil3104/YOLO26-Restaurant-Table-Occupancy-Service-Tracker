import React from 'react';
import { CentralKPIBanner } from '../CentralKPIBanner';
import { CentralRestaurantKPIs, ReportingScope, ShiftHistoricalSummary } from '../../types';

export interface CentralKpiPanelProps {
  central: CentralRestaurantKPIs;
  shiftHistory: ShiftHistoricalSummary;
  scope: ReportingScope;
  onScopeChange: (scope: ReportingScope) => void;
  freshnessSeconds?: number;
}

export const CentralKpiPanel: React.FC<CentralKpiPanelProps> = (props) => {
  return <CentralKPIBanner {...props} />;
};

export default React.memo(CentralKpiPanel);
