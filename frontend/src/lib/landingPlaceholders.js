// Temporary placeholder art for the landing while real Figma assets are pending.
// Swap these for S3-hosted exports later (see landingDesign.js usages).

export const LANDING_PLACEHOLDER_IMAGE =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='480' height='320'>
       <defs>
         <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
           <stop offset='0' stop-color='#8452FF'/>
           <stop offset='0.55' stop-color='#3A2A6B'/>
           <stop offset='1' stop-color='#0B0A10'/>
         </linearGradient>
       </defs>
       <rect width='480' height='320' rx='20' fill='url(#g)'/>
       <circle cx='370' cy='80' r='60' fill='#9B6BFF' opacity='0.25'/>
       <circle cx='110' cy='250' r='40' fill='#9B6BFF' opacity='0.18'/>
     </svg>`
  );

// Dark, cinematic hero backdrop (design hero is a dark photo, not a bright gradient).
export const LANDING_PLACEHOLDER_HERO =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='1440' height='900'>
       <defs>
         <radialGradient id='glow' cx='62%' cy='38%' r='55%'>
           <stop offset='0' stop-color='#8452FF' stop-opacity='0.55'/>
           <stop offset='0.45' stop-color='#3A2A6B' stop-opacity='0.35'/>
           <stop offset='1' stop-color='#0B0A10' stop-opacity='0'/>
         </radialGradient>
         <radialGradient id='warm' cx='30%' cy='30%' r='40%'>
           <stop offset='0' stop-color='#FF8A66' stop-opacity='0.18'/>
           <stop offset='1' stop-color='#0B0A10' stop-opacity='0'/>
         </radialGradient>
       </defs>
       <rect width='1440' height='900' fill='#0B0A10'/>
       <rect width='1440' height='900' fill='url(#warm)'/>
       <rect width='1440' height='900' fill='url(#glow)'/>
     </svg>`
  );

export const LANDING_PLACEHOLDER_AVATAR =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='96' height='96'>
       <defs>
         <linearGradient id='a' x1='0' y1='0' x2='1' y2='1'>
           <stop offset='0' stop-color='#9B6BFF'/>
           <stop offset='1' stop-color='#3A2A6B'/>
         </linearGradient>
       </defs>
       <circle cx='48' cy='48' r='48' fill='url(#a)'/>
       <circle cx='48' cy='38' r='16' fill='#0B0A10' opacity='0.35'/>
       <path d='M20 84c4-18 52-18 56 0' fill='#0B0A10' opacity='0.35'/>
     </svg>`
  );
