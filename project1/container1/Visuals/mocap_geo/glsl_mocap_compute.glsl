vec3 hsv2rgb(vec3 c) {
	vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
	return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
	const uint id = TDIndex();
	if (id >= TDNumElements())
		return;

	const int POSE_COUNT = 40;
	const int HAND_COUNT = 24;
	const int FACE_COUNT = 40;

	float x = 0.0;
	float y = 0.0;
	float z = 0.0;
	float alpha = 0.0;
	float huebase = 0.55;
	float sizeMult = 1.0;

	// gaia/mocap addressing is unstable (indices keep incrementing across
	// tracking sessions instead of reusing fixed landmark slots - see
	// MocapBridgeExt docstring), so these textures hold up to N currently
	// ACTIVE points, not stable per-joint identity. This shader just traces
	// the live shape, it never assumes slot i is always "the same joint".
	// Face channel naming is even less consistent (mixed zero-padding widths
	// sort out of numeric order alphabetically) so faceTex's grouping is a
	// weaker approximation than pose/hand - still an abstract shape trace,
	// not a literal face mesh reconstruction.
	if (id < uint(POSE_COUNT)) {
		int col = int(id);
		x = texelFetch(poseTex, ivec2(col, 0), 0).r;
		y = texelFetch(poseTex, ivec2(col, 1), 0).r;
		z = texelFetch(poseTex, ivec2(col, 2), 0).r;
		alpha = texelFetch(poseTex, ivec2(col, 3), 0).r;
		huebase = 0.55;
	} else if (id < uint(POSE_COUNT + HAND_COUNT)) {
		int col = int(id) - POSE_COUNT;
		x = texelFetch(handLTex, ivec2(col, 0), 0).r;
		y = texelFetch(handLTex, ivec2(col, 1), 0).r;
		z = texelFetch(handLTex, ivec2(col, 2), 0).r;
		alpha = texelFetch(handLTex, ivec2(col, 3), 0).r;
		huebase = 0.12;
		// Hands are only 24 points each vs face's 40, and read small next
		// to the now-consistently-full face cluster - modest boost so
		// hands don't disappear next to the face.
		sizeMult = 1.3;
	} else if (id < uint(POSE_COUNT + HAND_COUNT + HAND_COUNT)) {
		int col = int(id) - POSE_COUNT - HAND_COUNT;
		x = texelFetch(handRTex, ivec2(col, 0), 0).r;
		y = texelFetch(handRTex, ivec2(col, 1), 0).r;
		z = texelFetch(handRTex, ivec2(col, 2), 0).r;
		alpha = texelFetch(handRTex, ivec2(col, 3), 0).r;
		huebase = 0.92;
		sizeMult = 1.3;
	} else {
		int col = int(id) - POSE_COUNT - HAND_COUNT - HAND_COUNT;
		x = texelFetch(faceTex, ivec2(col, 0), 0).r;
		y = texelFetch(faceTex, ivec2(col, 1), 0).r;
		z = texelFetch(faceTex, ivec2(col, 2), 0).r;
		alpha = texelFetch(faceTex, ivec2(col, 3), 0).r;
		huebase = 0.75;
		// Face used to need a bigger boost (1.8) to read at all next to
		// pose/hands. Since the per-region budget fix (2026-08-03) face is
		// now reliably 40/40 populated across all regions, so it no longer
		// needs to outsize the other buckets - matches hands' 1.3 so no
		// single cluster dominates.
		sizeMult = 1.3;
	}

	// Mocap coords are normalized image space (0-1, y-down); recenter and
	// rescale into scene space. Time only adds a small idle drift on top -
	// it never replaces the live tracked position (seed-identity rule).
	vec3 pos;
	pos.x = (x - 0.5) * 1.5;
	pos.y = (0.5 - y) * 1.5 + 1.0;
	pos.z = z * 1.5;
	pos.x += sin(uTime * 0.5 + float(id) * 1.3) * 0.02 * alpha;
	pos.y += cos(uTime * 0.4 + float(id) * 2.1) * 0.02 * alpha;

	P[id] = pos;

	vec3 ownColor = hsv2rgb(vec3(huebase, 0.35, 1.0));
	vec3 moodColor = vec3(uMoodR, uMoodG, uMoodB);
	vec3 col = mix(ownColor, moodColor, 0.35);
	col = clamp(col, 0.0, 1.0);
	Color[id] = vec4(col, 1.0);

	// Dissolve, never a snap - PointScale rides the bridge's own
	// activity-decay alpha directly.
	// Raised the floor so lower-activity points still read as part of the
	// shape instead of dissolving to near-invisible (user reported only
	// seeing "a couple of dots" with the old 0.5*alpha curve).
	PointScale[id] = mix(0.15, 1.0, alpha) * 0.8 * sizeMult;
}
