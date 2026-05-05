import glfw
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
import numpy as np
import sys
import time

vertex_shader_source = """
#version 410 core
layout (location = 0) in vec2 aPos;
layout (location = 1) in vec2 aTexCoords;

out vec2 TexCoords;

void main()
{
    gl_Position = vec4(aPos.x, aPos.y, 0.0, 1.0);
    TexCoords = aTexCoords;
}
"""

fragment_shader_source = """
#version 410 core
out vec4 FragColor;
in vec2 TexCoords;

uniform vec2 iResolution;
uniform float iTime;
uniform vec3 iMouse;

const float M = 1.0;
const float R_s = 2.0 * M;
const float STEP_SIZE = 0.05;
const int MAX_STEPS = 400;

// Hash and Noise functions for procedural generation
float hash(float n) { return fract(sin(n) * 1e4); }
float noise(vec3 x) {
    vec3 p = floor(x);
    vec3 f = fract(x);
    f = f*f*(3.0-2.0*f);
    float n = p.x + p.y*57.0 + 113.0*p.z;
    return mix(mix(mix(hash(n+0.0), hash(n+1.0),f.x),
                   mix(hash(n+57.0), hash(n+58.0),f.x),f.y),
               mix(mix(hash(n+113.0), hash(n+114.0),f.x),
                   mix(hash(n+170.0), hash(n+171.0),f.x),f.y),f.z);
}

// Fractal Brownian Motion
float fbm(vec3 p) {
    float f = 0.0;
    f += 0.5000 * noise(p); p = p * 2.02;
    f += 0.2500 * noise(p); p = p * 2.03;
    f += 0.1250 * noise(p); p = p * 2.01;
    f += 0.0625 * noise(p);
    return f / 0.9375;
}

// Background starfield and nebula
vec3 starfield(vec3 dir) {
    vec3 color = vec3(0.0);
    
    // Stars
    float n = fbm(dir * 300.0);
    if (n > 0.85) {
        color += vec3(pow(n, 15.0));
    }
    
    // Milky way / Nebula band
    vec3 nebulaPos = dir * 4.0;
    float band = fbm(nebulaPos) * smoothstep(0.6, 0.0, abs(dir.y));
    color += vec3(0.1, 0.2, 0.4) * band * 0.8;
    color += vec3(0.3, 0.1, 0.2) * fbm(dir * 3.0 + vec3(1.0)) * band;
    
    return color;
}

// Accretion disk material
vec4 getAccretionDisk(vec3 p) {
    float r = length(p.xz);
    float innerR = 2.6 * M; // Photon ring starts around here
    float outerR = 12.0 * M;
    
    if (r < innerR || r > outerR) return vec4(0.0);
    
    // Density gradient
    float density = smoothstep(outerR, outerR * 0.5, r) * smoothstep(innerR, innerR * 1.5, r);
    
    // Rotation animation
    float angle = atan(p.z, p.x);
    float speed = 1.5 / sqrt(r); // Keplerian-ish velocity profile
    float t = iTime * speed;
    
    vec3 uv = vec3(r * 3.0, angle * 4.0 - t, 0.0);
    float n = fbm(uv);
    float n2 = fbm(uv * 2.0 + vec3(iTime * 0.2));
    
    // Disk Color Palette (hot gas)
    vec3 col = mix(vec3(1.0, 0.2, 0.05), vec3(1.0, 0.8, 0.4), n);
    col = mix(col, vec3(1.0, 0.9, 0.8), pow(n2, 3.0)); // Hot bright spots
    
    float alpha = density * (n * 0.7 + 0.3);
    
    // Opacity
    return vec4(col * alpha * 4.0, alpha); 
}

void main() {
    vec2 uv = TexCoords * 2.0 - 1.0;
    uv.x *= iResolution.x / iResolution.y;
    
    // Camera setup - interactive with mouse
    float camDist = 16.0;
    float camAngleX = iTime * 0.1;
    float camAngleY = 0.3; // Default elevation
    
    if (iMouse.z > 0.0) { // If mouse is clicked/dragged
        camAngleX = iMouse.x * 0.01;
        camAngleY = (iMouse.y * 0.01) - 3.0; // adjust mapping
        camAngleY = clamp(camAngleY, -1.5, 1.5);
    }
    
    vec3 ro = vec3(
        camDist * cos(camAngleY) * cos(camAngleX), 
        camDist * sin(camAngleY), 
        camDist * cos(camAngleY) * sin(camAngleX)
    );
    vec3 target = vec3(0.0, 0.0, 0.0);
    
    // Camera frame
    vec3 cw = normalize(target - ro);
    vec3 cp = vec3(0.0, 1.0, 0.0);
    vec3 cu = normalize(cross(cw, cp));
    vec3 cv = cross(cu, cw);
    
    vec3 rd = normalize(uv.x * cu + uv.y * cv + 1.5 * cw);
    
    vec3 p = ro;
    vec3 v = rd;
    
    // Conserved angular momentum squared
    float h2 = dot(cross(p, v), cross(p, v));
    
    vec3 color = vec3(0.0);
    float alpha = 1.0;
    
    // Raymarching Geodesics
    for (int i = 0; i < MAX_STEPS; i++) {
        float r = length(p);
        
        // Absorbed by Event horizon
        if (r < R_s * 1.0) { 
            break;
        }
        
        // Escape to infinity
        if (r > 35.0) {
            vec3 bg = starfield(normalize(v));
            color += alpha * bg;
            break;
        }
        
        // Adaptive step size: smaller near the black hole
        float dt = STEP_SIZE * (0.5 + r * 0.1); 
        
        // Gravity force (Schwarzschild acceleration approximation)
        vec3 a = -p * (1.5 * R_s * h2 / pow(r, 5.0));
        
        v += a * dt;
        vec3 next_p = p + v * dt;
        
        // Check Accretion Disk intersection (plane y=0)
        if ((p.y > 0.0 && next_p.y <= 0.0) || (p.y < 0.0 && next_p.y >= 0.0)) {
            float t_intersect = -p.y / v.y;
            vec3 p_intersect = p + v * t_intersect;
            
            vec4 diskCol = getAccretionDisk(p_intersect);
            
            if (diskCol.a > 0.01) {
                // Doppler shifting
                float r_intersect = length(p_intersect.xz);
                vec3 diskVel = normalize(vec3(-p_intersect.z, 0.0, p_intersect.x)) * sqrt(M / r_intersect);
                
                // Relativistic Doppler factor
                // D = sqrt(1 - v^2) / (1 - dot(v_ray, v_disk))
                float v_disk_mag = length(diskVel);
                float gamma = 1.0 / sqrt(max(0.01, 1.0 - v_disk_mag * v_disk_mag));
                float doppler = sqrt(1.0 - v_disk_mag*v_disk_mag) / (1.0 - dot(v, diskVel));
                
                // Emphasize the redshift/blueshift visually
                float shift = pow(doppler, 2.5);
                
                // Apply shift to RGB
                // Blue shift makes it bluer/brighter, Red shift makes it redder/dimmer
                diskCol.rgb *= vec3(shift * 0.8, shift, shift * 1.5);
                diskCol.rgb *= shift; // Intensity change
                
                color += alpha * diskCol.rgb * diskCol.a;
                alpha *= (1.0 - diskCol.a);
                
                // Early termination if opaque
                if (alpha < 0.01) break;
            }
        }
        
        p = next_p;
    }
    
    // Tonemapping (ACES-ish)
    color = (color * (2.51 * color + 0.03)) / (color * (2.43 * color + 0.59) + 0.14);
    
    // Gamma correction
    color = pow(color, vec3(1.0 / 2.2));
    
    FragColor = vec4(color, 1.0);
}
"""

def main():
    if not glfw.init():
        print("Failed to initialize GLFW")
        return

    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)
    glfw.window_hint(glfw.RESIZABLE, GL_TRUE)

    # Enable multisampling
    glfw.window_hint(glfw.SAMPLES, 4)

    window = glfw.create_window(1280, 720, "Schwarzschild Black Hole Raytracer", None, None)
    if not window:
        print("Failed to create GLFW window")
        glfw.terminate()
        return

    glfw.make_context_current(window)
    glfw.swap_interval(1) # V-sync

    print("OpenGL Version:", glGetString(GL_VERSION).decode())
    print("Renderer:", glGetString(GL_RENDERER).decode())

    # Quad vertices
    vertices = np.array([
        # positions   # texcoords
        -1.0, -1.0,   0.0, 0.0,
         1.0, -1.0,   1.0, 0.0,
        -1.0,  1.0,   0.0, 1.0,
         1.0,  1.0,   1.0, 1.0,
    ], dtype=np.float32)

    VAO = glGenVertexArrays(1)
    VBO = glGenBuffers(1)

    glBindVertexArray(VAO)
    glBindBuffer(GL_ARRAY_BUFFER, VBO)
    glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

    # Position attribute
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * vertices.itemsize, ctypes.c_void_p(0))
    glEnableVertexAttribArray(0)
    # TexCoord attribute
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * vertices.itemsize, ctypes.c_void_p(2 * vertices.itemsize))
    glEnableVertexAttribArray(1)

    # Compile shaders
    try:
        shader_program = compileProgram(
            compileShader(vertex_shader_source, GL_VERTEX_SHADER),
            compileShader(fragment_shader_source, GL_FRAGMENT_SHADER)
        )
    except Exception as e:
        print("Shader compilation failed:")
        print(e)
        glfw.terminate()
        return

    glBindBuffer(GL_ARRAY_BUFFER, 0)
    glBindVertexArray(0)

    # Get uniform locations
    res_loc = glGetUniformLocation(shader_program, "iResolution")
    time_loc = glGetUniformLocation(shader_program, "iTime")
    mouse_loc = glGetUniformLocation(shader_program, "iMouse")

    mouse_x, mouse_y = 0.0, 0.0
    mouse_pressed = False

    def cursor_pos_callback(win, xpos, ypos):
        nonlocal mouse_x, mouse_y
        if mouse_pressed:
            mouse_x = xpos
            mouse_y = ypos

    def mouse_button_callback(win, button, action, mods):
        nonlocal mouse_pressed, mouse_x, mouse_y
        if button == glfw.MOUSE_BUTTON_LEFT:
            if action == glfw.PRESS:
                mouse_pressed = True
                mouse_x, mouse_y = glfw.get_cursor_pos(win)
            elif action == glfw.RELEASE:
                mouse_pressed = False

    glfw.set_cursor_pos_callback(window, cursor_pos_callback)
    glfw.set_mouse_button_callback(window, mouse_button_callback)

    start_time = time.time()

    glEnable(GL_MULTISAMPLE)

    while not glfw.window_should_close(window):
        glfw.poll_events()

        width, height = glfw.get_framebuffer_size(window)
        glViewport(0, 0, width, height)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        glUseProgram(shader_program)

        current_time = time.time() - start_time
        glUniform1f(time_loc, current_time)
        glUniform2f(res_loc, width, height)
        glUniform3f(mouse_loc, mouse_x, mouse_y, 1.0 if mouse_pressed else 0.0)

        glBindVertexArray(VAO)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glBindVertexArray(0)

        glfw.swap_buffers(window)

    glfw.terminate()

if __name__ == '__main__':
    main()
