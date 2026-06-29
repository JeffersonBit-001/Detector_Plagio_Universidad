from django.contrib import admin
from django.contrib.auth.models import User
from .models import (
    Task, Cursos, Examen, EstadoExamen, Salon, 
    SalonAlumnos, PerfilBiometrico, IncidenciaExamen,
    Aula
)

# Register your models here.
class TaskAdmin(admin.ModelAdmin):
    readonly_fields = ('created', )

admin.site.register(Task, TaskAdmin)


# --- CONFIGURACIÓN DE INLINES ---
class SalonAlumnosInline(admin.TabularInline):
    """Permite matricular alumnos directamente desde la vista de edición del Salón"""
    model = SalonAlumnos
    extra = 3  # Número de filas vacías listas para llenar
    raw_id_fields = ['id_alumno']  # Optimiza la búsqueda de usuarios si la lista es enorme


# --- REGISTRO DE MODELOS DE INFRAESTRUCTURA ---

@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ('id_aula', 'nombre_aula')
    search_fields = ('nombre_aula',)

@admin.register(Cursos)
class CursosAdmin(admin.ModelAdmin):
    list_display = ('id_cursos', 'nombre_curso')
    search_fields = ('nombre_curso',)

@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ('nombre_salon', 'id_curso', 'aula_fisica', 'id_profesor')
    search_fields = ('nombre_salon', 'id_curso__nombre_curso', 'id_profesor__username', 'aula_fisica__nombre_aula')
    list_filter = ('id_curso', 'id_profesor', 'aula_fisica')
    
    # --- ¡AGREGA ESTA LÍNEA! ---
    readonly_fields = ('nombre_salon',)
    # ---------------------------
    
    inlines = [SalonAlumnosInline]

# --- REGISTRO DE MODELOS ACADÉMICOS Y AUDITORÍA ---

@admin.register(Examen)
class ExamenAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'id_curso', 'id_profesor', 'modo_tiempo', 'tiempo_base_minutos', 'tiempo_limite', 'is_visible')
    list_filter = ('modo_tiempo', 'is_visible', 'id_curso', 'id_profesor')
    search_fields = ('titulo', 'id_curso__nombre_curso', 'id_profesor__username')
    readonly_fields = ('tiempo_limite',)


@admin.register(EstadoExamen)
class EstadoExamenAdmin(admin.ModelAdmin):
    list_display = ('user', 'id_examen', 'estado', 'nota')
    list_filter = ('estado', 'id_examen')
    search_fields = ('user__username', 'id_examen__titulo')


# --- REGISTRO DE MODELOS DE SEGURIDAD (PROCTORING) ---

@admin.register(PerfilBiometrico)
class PerfilBiometricoAdmin(admin.ModelAdmin):
    list_display = ('user', 'fecha_registro')
    search_fields = ('user__username',)
    readonly_fields = ('fecha_registro',)


@admin.register(IncidenciaExamen)
class IncidenciaExamenAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'examen', 'tipo', 'minuto_ocurrencia', 'fecha')
    list_filter = ('tipo', 'fecha', 'examen')
    search_fields = ('alumno__username', 'examen__titulo')
    readonly_fields = ('fecha',)