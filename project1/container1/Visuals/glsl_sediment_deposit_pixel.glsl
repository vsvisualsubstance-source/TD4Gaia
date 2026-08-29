layout(location = 0) out vec4 fragColor;

vec3 seedHash3(float s) {
	float x = fract(sin(s * 127.1 + 1.0) * 43758.5453123);
	float y = fract(sin(s * 269.5 + 3.0) * 24634.6345231);
	float z = fract(sin(s * 419.2 + 7.0) * 39215.3141592);
	return vec3(x, y, z);
}

vec3 hsv2rgb(vec3 c) {
	vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
	vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
	return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
	vec2 uv = vUV.st;
	vec3 accum = vec3(0.0);

	// chopto_lexicon: row0=seedNorm, row1=countNorm, row2=alpha, 64 slots
	for (int i = 0; i < 64; i++) {
		float seedNorm = texelFetch(sTD2DInputs[0], ivec2(i, 0), 0).r;
		float countNorm = texelFetch(sTD2DInputs[0], ivec2(i, 1), 0).r;
		float alpha = texelFetch(sTD2DInputs[0], ivec2(i, 2), 0).r;
		if (alpha < 0.01)
			continue;

		// Deterministic 2D position from the seed alone - the same word
		// always deposits its mark in the same spot, per the seed-identity
		// rule, so recurring words visibly build up in place over time.
		vec3 h = seedHash3(seedNorm * 151.0 + 0.0003);
		vec2 pos = h.xy;

		// Correct for the non-square canvas so marks stay round in actual
		// pixels rather than stretching into ellipses.
		vec2 diff = uv - pos;
		diff.x *= (640.0 / 360.0);
		float d = length(diff);
		// Deliberately tiny: this deposits every frame for every currently
		// tracked word, and the feedback loop's steady-state value is
		// deposit/(1-decay) - with decay=0.995 that's a 200x multiplier, so
		// the per-frame deposit must stay small or a recurring word
		// saturates to white in seconds instead of building up faintly.
		float mark = smoothstep(0.035, 0.0, d) * (0.3 + 0.7 * countNorm) * alpha * 0.0015;
		vec3 col = hsv2rgb(vec3(seedNorm, 0.4, 0.9));
		accum += col * mark;
	}

	fragColor = TDOutputSwizzle(vec4(accum, 1.0));
}
