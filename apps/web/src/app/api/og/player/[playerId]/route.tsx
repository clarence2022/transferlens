import { ImageResponse } from 'next/og';
import { getPlayer } from '@/lib/api';

export const runtime = 'edge';

export async function GET(
  request: Request,
  { params }: { params: { playerId: string } }
) {
  try {
    const player = await getPlayer(params.playerId);
    const topPrediction = player.latest_predictions?.[0];
    
    const probability = topPrediction 
      ? `${(topPrediction.probability * 100).toFixed(0)}%`
      : 'N/A';
    
    const destination = topPrediction?.to_club_name || 'TBD';
    
    return new ImageResponse(
      (
        <div
          style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            backgroundColor: '#0a0a0a',
            padding: '48px',
            fontFamily: 'system-ui',
          }}
        >
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#ff6b00', fontWeight: 'bold', fontSize: '24px' }}>
                TRANSFER
              </span>
              <span style={{ color: '#ffffff', fontWeight: 'bold', fontSize: '24px' }}>
                LENS
              </span>
            </div>
            <span style={{ color: '#555555', fontSize: '14px' }}>
              transferlens.io
            </span>
          </div>
          
          {/* Content */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ fontSize: '48px', fontWeight: 'bold', color: '#ffffff' }}>
              {player.name}
            </div>
            <div style={{ fontSize: '20px', color: '#888888' }}>
              {player.current_club?.name || 'Free Agent'} • {player.position || 'N/A'}
            </div>
            
            {topPrediction && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '24px', marginTop: '24px' }}>
                <span style={{ color: '#ff6b00', fontSize: '32px' }}>→</span>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontSize: '24px', color: '#ffffff' }}>
                    {destination}
                  </span>
                  <span style={{ fontSize: '64px', fontWeight: 'bold', color: '#ff6b00' }}>
                    {probability}
                  </span>
                </div>
              </div>
            )}
          </div>
          
          {/* Footer */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: '#555555', fontSize: '14px' }}>
              Real-time transfer intelligence
            </span>
            <span style={{ color: '#555555', fontSize: '14px' }}>
              90-day probability
            </span>
          </div>
        </div>
      ),
      {
        width: 1200,
        height: 630,
      }
    );
  } catch (error) {
    // Return a fallback image
    return new ImageResponse(
      (
        <div
          style={{
            height: '100%',
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#0a0a0a',
            fontFamily: 'system-ui',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#ff6b00', fontWeight: 'bold', fontSize: '48px' }}>
              TRANSFER
            </span>
            <span style={{ color: '#ffffff', fontWeight: 'bold', fontSize: '48px' }}>
              LENS
            </span>
          </div>
          <div style={{ color: '#888888', fontSize: '24px', marginTop: '16px' }}>
            Real-time transfer intelligence
          </div>
        </div>
      ),
      {
        width: 1200,
        height: 630,
      }
    );
  }
}
