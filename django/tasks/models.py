from django.db import models
from django.contrib.auth.models import User
import uuid



class Cursos(models.Model):
    id_cursos = models.AutoField(primary_key=True)
    nombre_curso = models.CharField(max_length=255)
    #id_profesor = models.ForeignKey(
    #    User,
    #    on_delete=models.SET_NULL,
    #    db_column='id_profesor',
    #    blank=True,
    #    null=True
    #)

    class Meta:
        db_table = 'cursos'
        # managed = False  <--- ¡ELIMINADO!

    def __str__(self):
        return self.nombre_curso


class Aula(models.Model):
    id_aula = models.AutoField(primary_key=True)
    nombre_aula = models.CharField(
        max_length=100, 
        unique=True, 
        help_text="Ej: Pabellón A - 101, Laboratorio 3"
    )

    class Meta:
        db_table = 'aula'

    def __str__(self):
        return self.nombre_aula


class Examen(models.Model):
    id_examen = models.AutoField(primary_key=True)
    id_curso = models.ForeignKey('Cursos', on_delete=models.DO_NOTHING, db_column='id_curso')
    
    # --- ¡NUEVO CAMPO REQUERIDO! ---
    id_profesor = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        limit_choices_to={'is_staff': True},
        help_text="Profesor autor de este examen",
        null=True,  # ESTO ES LO QUE EVITA EL ERROR
        blank=True  # ESTO TAMBIÉN
    )
    # ------------------------------

    titulo = models.CharField(max_length=255)
    is_visible = models.BooleanField(default=True)
    cantidad_preguntas = models.IntegerField(default=0, help_text="0 para todas")




    # --- NUEVA ESTRUCTURA DE TIEMPO (3 CASOS) ---
    OPCIONES_TIEMPO = [
        ('LIBRE', 'Caso 1B: Tiempo General Libre (Sin límite por pregunta)'),
        ('REPARTIDO', 'Caso 1A: Tiempo General Repartido (Se divide entre preguntas)'),
        ('POR_PREGUNTA', 'Caso 2: Tiempo Fijo por Pregunta (Se suma al general)'),
    ]
    
    modo_tiempo = models.CharField(
        max_length=20, 
        choices=OPCIONES_TIEMPO, 
        default='LIBRE',
        verbose_name="Estrategia de Tiempo"
    )

    # Un solo campo numérico para evitar confusiones
    tiempo_base_minutos = models.IntegerField(
        default=0, 
        help_text="Ingrese los MINUTOS (Total o por Pregunta según lo que elijas arriba)."
    )
    
    # Campo interno para guardar el total calculado (sin que el usuario lo toque)
    tiempo_limite = models.IntegerField(default=0, editable=False)

    class Meta:
        db_table = 'examen'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        # Lógica automática al guardar
        total_q = self.cantidad_preguntas
        if total_q == 0:
            conteo = PreguntasExamen.objects.filter(id_examen=self.id_examen).count()
            total_q = conteo if conteo > 0 else 1

        # Calculamos el tiempo límite total real para la base de datos
        if self.modo_tiempo == 'POR_PREGUNTA':
            # Caso 2: (Minutos por pregunta) * Cantidad
            self.tiempo_limite = self.tiempo_base_minutos * total_q
        else:
            # Caso 1A y 1B: El número ingresado YA ES el total
            self.tiempo_limite = self.tiempo_base_minutos
            
        super(Examen, self).save(*args, **kwargs)




class Task(models.Model):
  title = models.CharField(max_length=200)
  description = models.TextField(max_length=1000)
  created = models.DateTimeField(auto_now_add=True)
  datecompleted = models.DateTimeField(null=True, blank=True)
  important = models.BooleanField(default=False)
  user = models.ForeignKey(User, on_delete=models.CASCADE)

  def __str__(self):
        return self.title + ' - ' + self.user.username

class PreguntasExamen(models.Model):
    id_preguntas_examen = models.AutoField(primary_key=True)
    id_examen = models.ForeignKey(Examen, on_delete=models.DO_NOTHING, db_column='id_examen')
    texto_pregunta = models.TextField()
    #texto_pregunta = models.CharField(max_length=255)

    # --- NUEVO: TIPO Y PUNTAJE ---
    TIPO_PREGUNTA = [
        ('M', 'Opción Múltiple (Automática)'),
        ('A', 'Abierta / Texto (Manual)'),
    ]
    
    tipo_pregunta = models.CharField(max_length=1, choices=TIPO_PREGUNTA, default='M')
    
    # Cuánto vale esta pregunta (Ej: 4 puntos, 1 punto, etc.)
    puntaje_maximo = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    # -----------------------------


    class Meta:
        db_table = 'preguntas_examen'
        # managed = False  <--- ¡ELIMINADO!

    def __str__(self):
        return f"[{self.get_tipo_pregunta_display()}] {self.texto_pregunta}"

class AlternativasExamen(models.Model):
    id_alternativas_examen = models.AutoField(primary_key=True)
    id_preguntas_examen = models.ForeignKey(
        PreguntasExamen, 
        on_delete=models.DO_NOTHING,
        db_column='id_preguntas_examen'
    )
    #texto_alternativa = models.CharField(max_length=255) 
    #texto_pregunta = models.TextField()
    texto_alternativa = models.TextField()
    valor = models.CharField(max_length=1)

    class Meta:
        db_table = 'alternativas_examen' 
        # managed = False  <--- ¡ELIMINADO!

    def __str__(self):
        return self.texto_alternativa

class EstadoExamen(models.Model):
    id_estado_examen = models.AutoField(primary_key=True)
    id_examen = models.ForeignKey(
        Examen, 
        on_delete=models.DO_NOTHING,
        db_column='id_examen'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        db_column='id_user'
    )
    estado = models.CharField(max_length=1, default='A')
    nota = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'estado_examen'
        # managed = False  <--- ¡ELIMINADO!
        constraints = [
            models.UniqueConstraint(fields=['user', 'id_examen'], name='unique_user_exam_status')
        ]

    def __str__(self):
        nota_str = f"Nota: {self.nota}" if self.nota is not None else f"Estado: {self.estado}"
        return f"{self.user.username} - Examen {self.id_examen.titulo} - {nota_str}"

class RespuestasUsuario(models.Model):
    id_respuesta = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        db_column='id_user'
    )
    id_examen = models.ForeignKey(
        Examen, 
        on_delete=models.CASCADE,
        db_column='id_examen'
    )
    id_preguntas_examen = models.ForeignKey(
        PreguntasExamen, 
        on_delete=models.CASCADE,
        db_column='id_preguntas_examen'
    )
    
    
    # --- MODIFICACIÓN IMPORTANTE: permitir NULL ---
    # Opción marcada (para tipo 'M')
    id_alternativas_examen = models.ForeignKey(
        AlternativasExamen, 
        on_delete=models.CASCADE, 
        db_column='id_alternativas_examen', 
        null=True, 
        blank=True
    )
    # ----------------------------------------------

    # --- NUEVOS CAMPOS ---
    respuesta_texto = models.TextField(null=True, blank=True, help_text="Respuesta escrita por el alumno")
    
    puntaje_obtenido = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, 
        help_text="Puntaje ganado en esta pregunta (auto o manual)"
    )
    
    comentario_profesor = models.TextField(null=True, blank=True, help_text="Feedback")
    # ------------------------------------------------



    class Meta:
        db_table = 'respuestas_usuario'
        constraints = [
            models.UniqueConstraint(fields=['user', 'id_examen', 'id_preguntas_examen'], name='respuesta_unica_por_pregunta')
        ]



class Salon(models.Model):
    id_salon = models.AutoField(primary_key=True)
    
    # Esto ya no es el espacio físico, es el nombre del grupo (Ej: "Grupo A", "Turno Noche")
    nombre_salon = models.CharField(max_length=100, help_text="Nombre de la sección o grupo") 
    
    # --- ¡NUEVA LLAVE FORÁNEA AL ESPACIO FÍSICO! ---
    aula_fisica = models.ForeignKey(
        Aula, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        help_text="Aula física donde se dicta la clase"
    )
    # -----------------------------------------------
    
    id_profesor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_profesor',
        limit_choices_to={'is_staff': True}, # Asegura que solo salgan profesores
        related_name='salones_gestionados'
    )
    
    id_curso = models.ForeignKey(
        Cursos,
        on_delete=models.CASCADE,
        db_column='id_curso',
        related_name='salones_asociados'
    )
    
    alumnos = models.ManyToManyField(
        User,
        related_name='salones_inscritos',
        through='SalonAlumnos'
    )

    class Meta:
        db_table = 'salon'

    def __str__(self):
        # Ahora el texto te dirá exactamente qué es cada cosa
        aula_str = self.aula_fisica.nombre_aula if self.aula_fisica else "Sin Aula"
        return f"{self.id_curso.nombre_curso} - {self.nombre_salon} ({aula_str}) - Prof. {self.id_profesor.username}"
    
    # 2. SOBRESCRIBIMOS EL MÉTODO SAVE PARA AUTOGENERAR EL CÓDIGO
    def save(self, *args, **kwargs):
        # Si el salón es nuevo y no tiene nombre, le inventamos un código
        if not self.nombre_salon:
            # Genera un código tipo: "SEC-9F2A1B"
            codigo_unico = uuid.uuid4().hex[:6].upper()
            self.nombre_salon = f"SEC-{codigo_unico}"
            
        super(Salon, self).save(*args, **kwargs)

# Modelo intermedio para la relación Many-to-Many entre Salon y User (alumnos)
class SalonAlumnos(models.Model):
    id_salonalumno = models.AutoField(primary_key=True) # ID para la tabla intermedia
    id_salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        db_column='id_salon'
    )
    id_alumno = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column='id_alumno'
    )
    # Puedes añadir otros campos aquí si en el futuro necesitas
    # información adicional sobre la inscripción de un alumno a un salón (ej. 'fecha_inscripcion')

    class Meta:
        db_table = 'salon_alumnos' # Nombre de la tabla en la BD
        unique_together = (('id_salon', 'id_alumno'),) # No puede haber el mismo alumno dos veces en el mismo salón

    def __str__(self):
        return f"Alumno {self.id_alumno.username} en {self.id_salon.nombre_salon}"    
    

# --- AGREGAR AL FINAL DE django/tasks/models.py ---
#---modelos de CAMARA E IA

class PerfilBiometrico(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    foto_referencia = models.ImageField(upload_to='biometria/referencias/', help_text="Foto oficial para comparar")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Biometría de {self.user.username}"

class IncidenciaExamen(models.Model):
    TIPOS_INCIDENCIA = [
        ('AUSENCIA', 'Usuario no detectado en cámara'),
        ('MULTIPLE', 'Múltiples personas detectadas'),
        ('SUPLANTACION', 'Rostro no coincide con el perfil'),
        ('CELULAR', 'Uso de celular detectado'), # Requiere modelo avanzado, pero dejamos la opción
    ]
    
    examen = models.ForeignKey(Examen, on_delete=models.CASCADE)
    alumno = models.ForeignKey(User, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=TIPOS_INCIDENCIA)
    minuto_ocurrencia = models.CharField(max_length=10, help_text="Ej: 10:45")
    evidencia = models.ImageField(upload_to='biometria/incidentes/', null=True, blank=True, help_text="Captura del momento")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'incidencias_examen'




# Asegúrate de agregar estas importaciones en la parte MÁS ALTA de tu models.py
from django.db.models.signals import post_save
from django.dispatch import receiver


# ... (Aquí están todas tus clases de modelos actuales) ...


# =========================================================
# --- SEÑALES (GATILLOS AUTOMÁTICOS) ---
# =========================================================

@receiver(post_save, sender=User)
def asignar_examen_de_prueba(sender, instance, created, **kwargs):
    """
    Se ejecuta automáticamente al crear un usuario.
    Busca estrictamente el curso de 'Inducción' para evitar confusiones.
    """
    if created and not instance.is_staff and not instance.is_superuser:
        try:
            # 1. Buscamos específicamente el curso que contenga la palabra "Inducción"
            curso_induccion = Cursos.objects.filter(nombre_curso__icontains="Inducción").first()
            
            if curso_induccion:
                # 2. Buscamos el salón que pertenece a ESE curso
                salon_induccion = Salon.objects.filter(id_curso=curso_induccion).first()
                
                # 3. Buscamos el examen que pertenece a ESE curso
                examen_prueba = Examen.objects.filter(id_curso=curso_induccion).first()
                
                # Si encontramos el salón y el examen, hacemos la matrícula
                if salon_induccion and examen_prueba:
                    
                    # Darle acceso al examen (Estado 'A')
                    EstadoExamen.objects.get_or_create(
                        user=instance, 
                        id_examen=examen_prueba, 
                        defaults={'estado': 'A'}
                    )
                    
                    # Matricularlo en el salón correcto
                    from .models import SalonAlumnos
                    SalonAlumnos.objects.get_or_create(
                        id_salon=salon_induccion, 
                        id_alumno=instance
                    )
        except Exception as e:
            print(f"Error asignando examen de prueba al usuario {instance.username}: {e}")