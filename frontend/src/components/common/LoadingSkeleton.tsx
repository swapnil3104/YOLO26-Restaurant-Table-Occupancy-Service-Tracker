import React from 'react';

interface LoadingSkeletonProps {
  height?: string | number;
  width?: string | number;
  borderRadius?: string;
  style?: React.CSSProperties;
  className?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  height = '100%',
  width = '100%',
  borderRadius = 'var(--radius-md, 8px)',
  style,
  className = '',
}) => {
  return (
    <div
      className={`skeleton-loader ${className}`}
      style={{
        height,
        width,
        borderRadius,
        background: 'linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        ...style,
      }}
    />
  );
};

export const CameraFeedSkeleton: React.FC<{ count?: number }> = ({ count = 4 }) => {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
      gap: '16px',
      width: '100%',
    }}>
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          style={{
            background: '#ffffff',
            borderRadius: 'var(--radius-lg, 12px)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            overflow: 'hidden',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            boxShadow: 'var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.05))',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <LoadingSkeleton height="18px" width="140px" />
            <LoadingSkeleton height="18px" width="70px" borderRadius="999px" />
          </div>
          <LoadingSkeleton height="220px" width="100%" borderRadius="8px" />
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <LoadingSkeleton height="14px" width="80px" />
            <LoadingSkeleton height="14px" width="110px" />
          </div>
        </div>
      ))}
    </div>
  );
};

export default LoadingSkeleton;
