import React from 'react';
import { FloorKPICards } from '../FloorKPICards';
import { FloorKPIItem } from '../../types';

export interface FloorKpiPanelProps {
  floors: FloorKPIItem[];
  selectedFloor: string;
  onSelectFloor: (floor: string) => void;
}

export const FloorKpiPanel: React.FC<FloorKpiPanelProps> = ({
  floors,
  selectedFloor,
  onSelectFloor,
}) => {
  return (
    <FloorKPICards
      floors={floors}
      activeFloorFilter={selectedFloor}
      onSelectFloor={onSelectFloor}
    />
  );
};

export default React.memo(FloorKpiPanel);
