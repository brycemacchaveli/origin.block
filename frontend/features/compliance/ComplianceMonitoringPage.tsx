
import React from 'react';
import Card from '../../components/Card';
import Badge from '../../components/Badge';
import Button from '../../components/Button';
import { mockComplianceEvents } from '../../services/mockData';
import { ComplianceEvent } from '../../types';

const ComplianceEventCard: React.FC<{ event: ComplianceEvent }> = ({ event }) => (
    <Card className="mb-3">
        <div className="flex flex-col sm:flex-row justify-between items-start gap-2">
            <div>
                <div className="flex items-center space-x-2">
                    <Badge status={event.eventType} />
                    <h3 className="font-semibold text-gray-800">{event.ruleName}</h3>
                </div>
                <p className="mt-2 text-sm text-gray-600">{event.details}</p>
                 <p className="mt-1 font-mono text-xs text-gray-500">
                    Affected: {event.affectedEntityType} ({event.affectedEntityId})
                </p>
            </div>
            <div className="text-left sm:text-right mt-2 sm:mt-0 flex-shrink-0">
                <p className="font-mono text-sm text-gray-500">{event.timestamp}</p>
                <Button variant="link" className="mt-1">View Details</Button>
            </div>
        </div>
    </Card>
);


const ComplianceMonitoringPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-sans font-bold text-gray-900 leading-tight text-2xl sm:text-3xl">Compliance Monitoring</h1>
        <p className="mt-1 font-sans text-base text-gray-600">Real-time feed of compliance and regulatory events.</p>
      </div>

      <div>
        {mockComplianceEvents.map(event => (
            <ComplianceEventCard key={event.id} event={event} />
        ))}
      </div>
    </div>
  );
};

export default ComplianceMonitoringPage;
