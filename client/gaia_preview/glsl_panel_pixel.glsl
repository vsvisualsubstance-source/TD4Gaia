// gaia_preview panel: cards, mood disc + bars (input 0 = soul, 1 row per
// channel), face landmarks scatter (input 1 = f* x,y,z interleaved, 1 row
// per channel). Text is composited on top by text_labels / text_word.
uniform vec4 uInfo;   // x = face point count (select_face channels / 3), y = 1 when a face is detected now
layout(location = 0) out vec4 fragColor;

const int MAX_FACE_PTS = 320;   // 2 persons x 152 contour points

float soul(int i) { return texelFetch(sTD2DInputs[0], ivec2(0, i), 0).r; }

float sdBox(vec2 p, vec2 c, vec2 h, float r) {
	vec2 d = abs(p - c) - h + r;
	return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r;
}

float fill(float d) { return 1.0 - smoothstep(-0.75, 0.75, d); }

void main() {
	vec2 p = vUV.st * uTDOutputInfo.res.zw;
	vec3 col = mix(vec3(0.050, 0.055, 0.065), vec3(0.080, 0.085, 0.095), vUV.t);

	float c1 = sdBox(p, vec2(230.0, 350.0), vec2(190.0, 300.0), 14.0);
	float c2 = sdBox(p, vec2(680.0, 350.0), vec2(220.0, 300.0), 14.0);
	float c3 = sdBox(p, vec2(1090.0, 350.0), vec2(150.0, 300.0), 14.0);
	col = mix(col, vec3(0.105, 0.110, 0.125), fill(min(c1, min(c2, c3))));

	vec3 mood = clamp(vec3(soul(0), soul(1), soul(2)), 0.0, 1.0);
	float d = length(p - vec2(230.0, 470.0)) - 100.0;
	col += mood * 0.12 * exp(-max(d, 0.0) / 30.0) * fill(c1);
	col = mix(col, mood, fill(d));

	vec3 accent = mix(mood, vec3(0.92, 0.90, 0.86), 0.35);
	for (int i = 0; i < 6; i++) {
		float y = 300.0 - float(i) * 40.0;
		float v = clamp(soul(3 + i), 0.0, 1.0);
		col = mix(col, vec3(0.19, 0.20, 0.22), fill(sdBox(p, vec2(230.0, y), vec2(150.0, 3.0), 3.0)));
		float w = max(150.0 * v, 3.0);
		col = mix(col, accent, step(0.001, v) * fill(sdBox(p, vec2(80.0 + w, y), vec2(w, 3.0), 3.0)));
	}

	vec2 fo = vec2(960.0, 80.0);
	vec2 fs = vec2(260.0, 195.0);   // camera frame, 4:3
	float fp = sdBox(p, fo + fs * 0.5, fs * 0.5, 8.0);
	col = mix(col, vec3(0.075, 0.080, 0.090), fill(fp));
#if TD_NUM_2D_INPUTS > 1
	if (fp < 0.0) {
		int n = int(uInfo.x);
		float acc = 0.0;
		for (int i = 0; i < MAX_FACE_PTS; i++) {
			if (i >= n) break;
			float fx = texelFetch(sTD2DInputs[1], ivec2(0, i * 3), 0).r;
			float fy = texelFetch(sTD2DInputs[1], ivec2(0, i * 3 + 1), 0).r;
			acc += 1.0 - smoothstep(0.8, 1.8, length(p - (fo + vec2(fx, 1.0 - fy) * fs)));
		}
		// oscin_mocap never expires channels: stale points stay, drawn dim
		col = mix(col, accent, clamp(acc, 0.0, 1.0) * mix(0.25, 1.0, uInfo.y));
	}
#endif
	fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
