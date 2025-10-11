
import React from 'react';
import { LoanStatus, KycStatus, ComplianceEventType } from '../types';

type BadgeProps = {
  status: LoanStatus | KycStatus | ComplianceEventType;
};

const statusColors: Record<string, string> = {
  [LoanStatus.Approved]: 'bg-green-100 text-green-800',
  [LoanStatus.UnderReview]: 'bg-yellow-100 text-yellow-800',
  [LoanStatus.Pending]: 'bg-yellow-100 text-yellow-800',
  [LoanStatus.Rejected]: 'bg-red-100 text-red-800',
  [KycStatus.Verified]: 'bg-green-100 text-green-800',
  // FIX: Removed duplicate key. Both `LoanStatus.Pending` and `KycStatus.Pending` resolve to "Pending".
  [KycStatus.Failed]: 'bg-red-100 text-red-800',
  [ComplianceEventType.Success]: 'bg-green-100 text-green-800',
  [ComplianceEventType.Alert]: 'bg-yellow-100 text-yellow-800',
  [ComplianceEventType.Violation]: 'bg-red-100 text-red-800',
};

const Badge: React.FC<BadgeProps> = ({ status }) => {
  const colorClass = statusColors[status] || 'bg-gray-100 text-gray-800';
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
      {status}
    </span>
  );
};

export default Badge;