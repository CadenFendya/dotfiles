#version 300 es
// Screen-wide color vibrance, like NVIDIA Digital Vibrance.
// VIBRANCE: 0.5 = normal colors (50%), 1.0 = maximum (100%). 0.75 = 75%.
precision highp float;

in vec2 v_texcoord;
uniform sampler2D tex;
out vec4 fragColor;

const float VIBRANCE = 0.75;

void main() {
    vec4 pixel = texture(tex, v_texcoord);
    // 50% -> 1.0x saturation, 100% -> 2.0x
    float strength = (VIBRANCE - 0.5) * 2.0;

    float luma = dot(pixel.rgb, vec3(0.2126, 0.7152, 0.0722));
    float maxC = max(pixel.r, max(pixel.g, pixel.b));
    float minC = min(pixel.r, min(pixel.g, pixel.b));
    float sat = maxC - minC;

    // Boost dull colors more than already-saturated ones so skin tones don't blow out
    float boost = 1.0 + strength * (1.0 - sat);
    fragColor = vec4(clamp(mix(vec3(luma), pixel.rgb, boost), 0.0, 1.0), pixel.a);
}
