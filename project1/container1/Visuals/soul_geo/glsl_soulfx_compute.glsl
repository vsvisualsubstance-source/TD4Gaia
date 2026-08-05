// Cheap stable hash - still used for a SMALL residual per-point texture
// (anti-banding) and for twinkle phase/speed desync, which carry no
// "meaning" so stay decorative. The DOMINANT per-point variation (hue,
// brightness) now comes from real per-room sensor data (see below),
// replacing the fully-decorative jitter this shader used before
// 2026-08-05.
uint hash11(uint x) {
	x ^= x >> 16;
	x *= 0x7feb352du;
	x ^= x >> 15;
	x *= 0x846ca68bu;
	x ^= x >> 16;
	return x;
}
float hashFloat(uint seed) {
	return float(hash11(seed)) / 4294967295.0;
}

// Public-domain RGB<->HSV (Sam Hocevar) - lets us rotate hue without
// disturbing the value/rim shading already tuned below.
vec3 rgb2hsv(vec3 c) {
	vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
	vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = q.x - min(q.w, q.y);
	float e = 1.0e-10;
	return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}
vec3 hsv2rgb(vec3 c) {
	vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
	return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
	const uint id = TDIndex();
	if (id >= TDNumElements())
		return;

	vec3 p = TDIn_P();

	// Which of the 4 ROOMS sector this point falls in, purely from its
	// own angle around the sphere's Y axis - not from point id. This
	// keeps each room's group spatially contiguous (a wedge of the
	// sphere), matching zones_geo/plantnotes_geo/recognition_geo's
	// existing room-sector convention, instead of a scattered mapping.
	float angle01 = atan(p.z, p.x) / 6.28318530718;
	angle01 = fract(angle01 + 1.0); // atan2 range is -pi..pi -> wrap to 0..1
	int roomIdx = int(clamp(floor(angle01 * 4.0), 0.0, 3.0));

	// roomTex is a 16-row, 1-col texture: 4 tempNorm, 4 hasTemp,
	// 4 darkness, 4 presenceNorm (script_room_env_tex's fixed channel
	// order, ROOMS order = corridoio, ingresso, salotto, soggiorno).
	float tempNorm = texelFetch(roomTex, ivec2(0, roomIdx), 0).r;
	float hasTemp = texelFetch(roomTex, ivec2(0, roomIdx + 4), 0).r;
	float darkness = texelFetch(roomTex, ivec2(0, roomIdx + 8), 0).r;
	float presenceNorm = texelFetch(roomTex, ivec2(0, roomIdx + 12), 0).r;
	float activityLevel = texelFetch(roomTex, ivec2(0, roomIdx + 16), 0).r;

	// lightTex is the same 4-room layout: 4 r, 4 g, 4 b, 4 powerOn - the
	// room's real Hue light color (HSB->RGB, converted on the Python
	// side), only meaningful when powerOn=1 (registry.GetRoomLighting
	// returns (0,0,0,0) for an off or unmapped-room light rather than a
	// fabricated color).
	vec3 lightColor = vec3(
		texelFetch(lightTex, ivec2(0, roomIdx), 0).r,
		texelFetch(lightTex, ivec2(0, roomIdx + 4), 0).r,
		texelFetch(lightTex, ivec2(0, roomIdx + 8), 0).r
	);
	float lightPowerOn = texelFetch(lightTex, ivec2(0, roomIdx + 12), 0).r;

	// Small residual hash texture so points within the same room sector
	// still read as individual sparkles, not a flat solid wedge - kept
	// deliberately subtle so the room signal (real data) stays dominant.
	float hueNoise = (hashFloat(hash11(id * 5u + 0u)) - 0.5) * 0.03;
	float valNoise = mix(0.92, 1.08, hashFloat(hash11(id * 5u + 1u)));
	float sizeNoise = mix(0.9, 1.1, hashFloat(hash11(id * 5u + 2u)));
	float phaseJitter = hashFloat(hash11(id * 5u + 3u)) * 6.2831853;
	float speedJitter = mix(0.6, 1.4, hashFloat(hash11(id * 5u + 4u)));

	// Room activity speeds up that sector's breathing - a "working" or
	// "present" room pulses faster than an "idle"/"empty" one.
	// uLifeIndex (Gaia's own 0-100 vitality, sampled globally) scales
	// the breathing AMPLITUDE for every point - a livelier Gaia breathes
	// more visibly everywhere, on top of each sector's own pace. Base
	// amplitude stays small on purpose (see finishing rule: restraint
	// over motion) even at lifeIndex=1.0.
	float activitySpeed = mix(0.5, 2.0, activityLevel);
	float breatheAmp = 0.06 + 0.14 * uLifeIndex;
	float twinkle = (1.0 - breatheAmp) + breatheAmp * sin(uTime * 0.6 * speedJitter * activitySpeed + phaseJitter);

	float r = length(p);
	float rim = smoothstep(0.55, 1.15, r);

	// Was blue (0.15,0.45,0.95) - swapped to green per user request
	// 2026-08-03, same peak channel magnitude (0.95) so the rim anti-clip
	// tuning above (which assumes a 0.95 peak) still holds without redoing
	// that math.
	vec3 coolColor = vec3(0.12, 0.95, 0.35);
	vec3 warmColor = vec3(0.95, 0.28, 0.12);
	// uSmile shifts the base mix itself toward warmColor (not just an additive
	// boost on top) - coolColor's blue channel is already near-max, so adding
	// warm channels on top of unchanged blue read as pale/cyan, not warm.
	// Sliding the mix is what actually changes the perceived hue.
	float mixAmt = clamp(uStress - uCalm * 0.6 + uSmile * 0.55, 0.0, 1.0);
	vec3 base = mix(coolColor, warmColor, mixAmt);

	// Per-room hue rotation from real temperature (colder room -> shifted
	// toward cool, warmer room -> shifted toward warm), on top of the
	// mood family established above - plus the small per-point residual.
	// hasTemp==0 means tempNorm sits at its neutral 0.5 fallback, so this
	// term is naturally ~0 for rooms without a sensor instead of guessing.
	float tempHueShift = (tempNorm - 0.5) * 0.20;
	vec3 baseHsv = rgb2hsv(base);
	baseHsv.x = fract(baseHsv.x + tempHueShift + hueNoise);
	base = hsv2rgb(baseHsv);

	// Rim factor capped so the brightest channel (coolColor's blue, 0.95)
	// never quite reaches 1.0 even at full rim (0.95*0.8=0.76) - the old
	// 0.55+0.65 range (max 1.2x) clipped individual points to pure white
	// at the rim, and with hundreds of additively-overlapping points that
	// per-point clipping compounded into a flat white shell with no
	// visible internal texture/gradient (confirmed via render1 capture
	// 2026-08-03, before any bloom was even applied).
	vec3 col = base * (0.35 + 0.35 * rim) + vec3(uEnergy * 0.12);
	col += vec3(0.06, 0.05, 0.04) * uPeoplePresent; // subtle YOLO presence boost
	col += vec3(0.18, 0.1, 0.02) * uSmile;          // MediaPipe: extra warm glow on top of the hue shift above (amplified per user request - was barely perceptible at 0.12/0.09/0.025)
	col *= mix(0.2, 1.0, uEyesOpen);                // MediaPipe: pronounced dim when eyes closed (was mix(0.6,1.0,...), too subtle to read)

	// Real Hue light color tint, per room - only when that room's light
	// is actually on (lightPowerOn from registry.GetRoomLighting, never
	// fabricated for an off/unmapped room). Kept a secondary blend
	// (0.35 max) so the mood/temperature identity above stays dominant -
	// this is meant to read as "that side of the sphere reflects the
	// room's real light", not replace the sphere's own color language.
	col = mix(col, lightColor, lightPowerOn * 0.35);

	// Real per-room dim/boost: darker room reads dimmer, a room with
	// people present reads a touch brighter - on top of the small
	// per-point residual (valNoise) and the slow twinkle breathing.
	float roomVal = mix(1.0, 0.55, darkness) * mix(0.85, 1.15, presenceNorm) * mix(0.9, 1.1, activityLevel);
	col *= roomVal * valNoise * twinkle;

	// Whole-house "aliveness" - how lit/occupied the home is right now
	// (gaia/metrics/*), a physical complement to Gaia's own internal
	// lifeIndex above. Small additive glow, global rather than
	// per-room, so it reads as ambient atmosphere, not another sector.
	float houseAliveness = (uActiveLights + uActivePeople + uAverageLight) / 3.0;
	col += vec3(0.05, 0.045, 0.03) * houseAliveness;

	col = clamp(col, 0.0, 1.0);                     // keep the mood mix visible - additive point blending amplifies any unclamped overshoot into a flat white sphere
	Color[id] = vec4(col, 1.0);

	// Presence nudges point size too, alongside the small hash residual.
	PointScale[id] = (0.5 + 1.6 * rim + 0.7 * uEnergy + 0.25 * uPeoplePresent + 0.5 * uSmile) * sizeNoise * mix(0.95, 1.1, presenceNorm);
}
