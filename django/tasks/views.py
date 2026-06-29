from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from django.contrib.auth.decorators import login_required
# --- ¡IMPORTACIONES MODIFICADAS! ---
from .models import Task, AlternativasExamen, PreguntasExamen, EstadoExamen,Examen, RespuestasUsuario, Cursos, Salon, SalonAlumnos, User,PerfilBiometrico,IncidenciaExamen
from .forms import TaskForm
import pandas as pd
import re
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.cache import never_cache # <--- ¡IMPORTACIÓN AÑADIDA!
import json
import random
from .forms import ExamenForm,CursoForm,PreguntaForm,AlternativaForm,SalonForm



from django.views.decorators.csrf import csrf_exempt # <--- ¡AÑADE ESTA IMPORTACIÓN!

from django.contrib.auth.decorators import user_passes_test

from django.db import transaction # <-- ¡AÑADE ESTA IMPORTACIÓN!

from django.core.files.base import ContentFile
import base64

# --- (Las vistas home, signup, tasks, etc. no cambian) ---
# Modifica la vista home agregando el decorador
@never_cache
@login_required(login_url='signin')  # <--- AGREGA ESTA LÍNEA
def home(request):
    # Si el usuario ya inició sesión, redirigirlo a su dashboard
    if request.user.is_authenticated:
        # Aquí puedes filtrar si es profesor o alumno si tienes esa distinción
        # Por ejemplo, si usas grupos o un campo en el modelo:
        if request.user.is_staff: # O tu lógica para detectar profesor
             return redirect('professor_dashboard')
        else:
             return redirect('exam/dashboard/') # O 'exam_dashboard', la ruta de tus alumnos
            
    # Si no ha iniciado sesión, mostrar la página de inicio normal
    return render(request, 'home.html')



def signup(request):
    if request.user.is_authenticated:
        return redirect('exam_dashboard') # O redirige a 'home' si prefieres
    # --------------------------------

    if request.method == 'GET':
        return render(request, 'signup.html', {"form": UserCreationForm})
    else:
        if request.POST["password1"] == request.POST["password2"]:
            try:
                user = User.objects.create_user(
                    request.POST["username"], password=request.POST["password1"])
                user.save()
                login(request, user)
                return redirect('exam_dashboard')
            except IntegrityError:
                return render(request, 'signup.html', {
                    "form": UserCreationForm, "error": 
                    "Username already exists."})
        return render(request, 'signup.html', {"form": UserCreationForm, "error": "Passwords did not match."})
@login_required
def tasks(request):
    tasks = Task.objects.filter(user=request.user, datecompleted__isnull=True)
    return render(request, 'tasks.html', {"tasks": tasks})
@login_required
def tasks_completed(request):
    tasks = Task.objects.filter(user=request.user, datecompleted__isnull=False).order_by('-datecompleted')
    return render(request, 'tasks.html', {"tasks": tasks})
@login_required
def create_task(request):
    if request.method == "GET":
        return render(request, 'create_task.html', {"form": TaskForm})
    else:
        try:
            form = TaskForm(request.POST)
            new_task = form.save(commit=False)
            new_task.user = request.user
            new_task.save()
            return redirect('tasks')
        except ValueError:
            return render(request, 'create_task.html', {"form": TaskForm, "error": "Error creating task."})
@login_required
def signout(request):
    logout(request)
    return redirect('signin')

# --- VISTA SIGNIN MODIFICADA ---
@never_cache
def signin(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('professor_dashboard')
        else:
            return redirect('exam_dashboard')
    # --------------------------------


    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                
                # --- ¡LÓGICA DE REDIRECCIÓN POR ROL! ---
                if user.is_staff:
                    # Si es Profesor, llévalo a su panel
                    return redirect('professor_dashboard') # Crearemos esta ruta
                else:
                    # Si es Alumno, llévalo al panel de exámenes
                    return redirect('exam_dashboard') 
                # --- FIN DE LA LÓGICA ---
                
            else:
                messages.error(request, "Usuario o contraseña inválidos.")
        else:
            messages.error(request, "Usuario o contraseña inválidos.")
    form = AuthenticationForm()
    return render(request, 'signin.html', {'form': form})

# --- (Vistas de tasks... no cambian) ---
@login_required
def task_detail(request, task_id):
    if request.method == 'GET':
        task = get_object_or_404(Task, pk=task_id, user=request.user)
        form = TaskForm(instance=task)
        return render(request, 'task_detail.html', {'task': task, 'form': form})
    else:
        try:
            task = get_object_or_404(Task, pk=task_id, user=request.user)
            form = TaskForm(request.POST, instance=task)
            form.save()
            return redirect('tasks')
        except ValueError:
            return render(request, 'task_detail.html', {'task': task, 'form': form, 'error': 'Error updating task.'})
@login_required
def complete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    if request.method == 'POST':
        task.datecompleted = timezone.now()
        task.save()
        return redirect('tasks')
@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id, user=request.user)
    if request.method == 'POST':
        task.delete()
        return redirect('tasks')
def examen(request):
    lista_de_preguntas = PreguntasExamen.objects.prefetch_related('alternativasexamen_set').all()
    context = { 'preguntas': lista_de_preguntas }
    return render(request, 'examen.html', context)

##########################################################
# --- ¡ARQUITECTURA DE EXÁMENES MODIFICADA! ---
##########################################################

# --- (La función check_exam_status se queda igual) ---
def check_exam_status(user, examen_id):
    """
    Chequea el estado ('A' o 'D') para un usuario Y un examen específico.
    """
    estado_obj, created = EstadoExamen.objects.get_or_create(
        user=user,
        id_examen_id=examen_id,
        defaults={'estado': 'A'} 
    )
    return estado_obj.estado

# --- ¡VISTA MODIFICADA! ---

@never_cache
@login_required
def exam_dashboard(request):
    """
    Dashboard del alumno organizado por CURSOS.
    Evita duplicados si el alumno está en varios salones del mismo curso.
    """
    # 1. Obtener los salones donde el usuario está inscrito
    mis_salones = request.user.salones_inscritos.select_related('id_curso').all()

    # 2. Extraer los CURSOS ÚNICOS de esos salones
    # Usamos un diccionario {id_curso: objeto_curso} para evitar duplicados
    cursos_dict = {}
    for salon in mis_salones:
        if salon.id_curso.id_cursos not in cursos_dict:
            cursos_dict[salon.id_curso.id_cursos] = salon.id_curso

    # 3. Obtener las asignaciones visibles de este usuario para estos cursos
    cursos_ids = list(cursos_dict.keys())
    asignaciones = EstadoExamen.objects.filter(
        user=request.user,
        id_examen__is_visible=True,
        id_examen__id_curso_id__in=cursos_ids
    ).select_related('id_examen')

    # 4. Organizar los datos agrupándolos por CURSO
    # Formato: [ { 'curso': curso_obj, 'examenes': [lista_datos] }, ... ]
    dashboard_data = []

    for curso_id, curso_obj in cursos_dict.items():
        examenes_del_curso = []
        
        # Filtramos las asignaciones que pertenecen a este curso
        for asignacion in asignaciones:
            if asignacion.id_examen.id_curso_id == curso_id:
                examenes_del_curso.append({
                    'examen': asignacion.id_examen,
                    'estado': asignacion.estado,
                    'nota': asignacion.nota
                })
        
        # Añadimos el curso al dashboard
        dashboard_data.append({
            'curso': curso_obj,
            'examenes': examenes_del_curso
        })

    context = {
        'dashboard_data': dashboard_data
    }
    return render(request, 'exam_dashboard.html', context)
#----------------------------------------------------+

# --- ¡VISTA MODIFICADA! ---
@never_cache 
@login_required
def welcome_exam(request, examen_id):

    # --- VERIFICACIÓN BIOMÉTRICA PREVIA ---
    if not PerfilBiometrico.objects.filter(user=request.user).exists():
        # Si no tiene foto, lo mandamos a enrolarse y le pasamos el examen al que quería ir
        return redirect(f'/enrolamiento/?next_exam={examen_id}')
    # --------------------------------------



    estado = check_exam_status(request.user, examen_id)
    
    # --- ¡AÑADE ESTA VERIFICACIÓN! ---
    if estado == 'F':
        messages.info(request, 'Ya has completado este examen.')
        return redirect('exam_dashboard') 
    # --- FIN DE LA ADICIÓN ---

    if estado == 'D':
        messages.error(request, f'Ya no tienes acceso al examen {examen_id}.')
        return redirect('exam_dashboard') 
        
    return render(request, 'welcome_exam.html', {'examen_id': examen_id})



# --- ¡VISTA MODIFICADA! ---
@never_cache 
@login_required
def exam_page(request, examen_id):
    # 1. Obtener el examen
    examen = get_object_or_404(Examen, pk=examen_id)



    # ====================================================
    # --- Seguridad ---
    # Verificar si el alumno terminó
    # ====================================================
    estado_actual = check_exam_status(request.user, examen_id)
    
    if estado_actual == 'F':
        messages.info(request, "Ya has finalizado este examen.") # Mensaje informativo
        return redirect('exam_dashboard')
    
    if estado_actual == 'D':
        messages.error(request, "Este examen está bloqueado o ha sido cancelado.") # Mensaje de error
        return redirect('exam_dashboard')
    # ====================================================



    
    # 2. Definir una clave única para la sesión
    session_key = f'exam_{examen_id}_questions_order_{request.user.id}'

    # 3. Verificar si ya tiene preguntas asignadas en su sesión
    if session_key in request.session:
        selected_ids = request.session[session_key]
        preguntas_queryset = PreguntasExamen.objects.filter(pk__in=selected_ids)
        preguntas = sorted(preguntas_queryset, key=lambda q: selected_ids.index(q.pk))
    else:
        # 4. Si es la primera vez: GENERAR NUEVO SORTEO
        all_ids = list(PreguntasExamen.objects.filter(id_examen=examen).values_list('id_preguntas_examen', flat=True))
        limit = examen.cantidad_preguntas
        
        if limit > 0 and limit < len(all_ids):
            selected_ids = random.sample(all_ids, limit)
        else:
            selected_ids = all_ids
            random.shuffle(selected_ids)
            
        request.session[session_key] = selected_ids
        preguntas_queryset = PreguntasExamen.objects.filter(pk__in=selected_ids)
        preguntas = sorted(preguntas_queryset, key=lambda q: selected_ids.index(q.pk))

    # ==============================================================================
    # 5. LÓGICA DE TIEMPOS (¡AQUÍ ES DONDE LA APLICAS!)
    # ==============================================================================
    
    tiempo_pregunta_segundos = 0
    usar_timer_pregunta = False
    
    total_preguntas_reales = len(preguntas)
    if total_preguntas_reales == 0: total_preguntas_reales = 1

    # CASO 2: Tiempo Fijo por Pregunta
    if examen.modo_tiempo == 'POR_PREGUNTA':
        tiempo_pregunta_segundos = examen.tiempo_base_minutos * 60 
        usar_timer_pregunta = True

    # CASO 1A: Tiempo General Repartido
    elif examen.modo_tiempo == 'REPARTIDO':
        # Convertimos el total a segundos y dividimos
        total_segundos = examen.tiempo_base_minutos * 60
        tiempo_pregunta_segundos = int(total_segundos / total_preguntas_reales)
        usar_timer_pregunta = True
        
    # CASO 1B ('LIBRE'): usar_timer_pregunta se queda en False.

    return render(request, 'home.html', {
        'examen': examen,
        'preguntas': preguntas,
        'examen_id': examen_id,
        'tiempo_pregunta': tiempo_pregunta_segundos, 
        'usar_timer_pregunta': usar_timer_pregunta,
    })

# --- (La vista cancel_exam se queda igual) ---
@login_required
def cancel_exam(request):
    # ... (El código de esta vista se queda igual) ...
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            examen_id = data.get('examen_id')
            if not examen_id:
                return JsonResponse({'status': 'error', 'message': 'Falta examen_id'}, status=400)
            estado_obj, created = EstadoExamen.objects.get_or_create(
                user=request.user,
                id_examen_id=examen_id
            )
            estado_obj.estado = 'D'
            estado_obj.save()
            print(f"Examen {examen_id} cancelado para el usuario {request.user.username}")
            return JsonResponse({'status': 'success', 'message': f'Estado actualizado a D para el examen {examen_id}'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    


    # ... (Añade esto al final de tu tasks/views.py)



# ... (Añade esto al final de tu tasks/views.py)
#@csrf_exempt # <--- ¡AÑADE ESTE DECORADOR!
@login_required
def submit_exam(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            examen_id = data.get('examen_id')
            respuestas_enviadas = data.get('respuestas') # Lista [{pregunta: 1, alternativa: 2}, ...]
            user = request.user

            if not examen_id:
                return JsonResponse({'status': 'error', 'message': 'Faltan datos'}, status=400)

            examen_obj = get_object_or_404(Examen, pk=examen_id)

            # 1. RECUPERAR LAS PREGUNTAS ASIGNADAS (De la sesión)
            session_key = f'exam_{examen_id}_questions_order_{user.id}'
            assigned_question_ids = request.session.get(session_key, [])

            # Fallback de seguridad: Si por alguna razón extrema se borró la sesión,
            # recuperamos todas las del examen para no dejar al alumno con 0.
            if not assigned_question_ids:
                assigned_question_ids = list(PreguntasExamen.objects.filter(id_examen_id=examen_id).values_list('id_preguntas_examen', flat=True))

            # 2. CREAR MAPA DE RESPUESTAS ENVIADAS para búsqueda rápida
            # { 'ID_PREGUNTA_STR': 'ID_ALTERNATIVA' }
            #mapa_respuestas = {str(r['pregunta']): r['alternativa'] for r in respuestas_enviadas}
            mapa_respuestas = {str(r['pregunta']): r for r in data.get('respuestas', [])}


            correct_answers = 0
            # Calificamos sobre el total de preguntas que SE LE ASIGNARON al alumno
            total_questions_to_grade = len(assigned_question_ids)

            
            with transaction.atomic():
                for p_id in assigned_question_ids: # (Usar lógica de ids asignados como tenías)
                    p_id_str = str(p_id)
                    dato = mapa_respuestas.get(p_id_str)
                    
                    alt_id = None
                    texto = None
                    
                    # Detectar si es texto o ID
                    # Detectar datos (Corregido para leer texto explícito)
                    if dato:
                        # 1. Intentamos leer el campo de texto explícito
                        texto_enviado = dato.get('respuesta_texto') 
                        
                        # 2. Leemos el campo de alternativa
                        val = dato.get('alternativa') 

                        # LÓGICA DE ASIGNACIÓN
                        if val and str(val).isdigit(): 
                            # Si 'alternativa' es un número, es un ID de opción múltiple
                            alt_id = val
                            # Si también enviaron texto (raro pero posible), lo guardamos
                            if texto_enviado:
                                texto = texto_enviado
                        else:
                            # Si 'alternativa' NO es número, asumimos que usaron ese campo para enviar el texto
                            # O usamos el campo 'respuesta_texto' si existe.
                            texto = texto_enviado if texto_enviado else val

                    # Guardar
                    RespuestasUsuario.objects.update_or_create(
                        user=user,
                        id_examen_id=examen_id,
                        id_preguntas_examen_id=p_id,
                        defaults={
                            'id_alternativas_examen_id': alt_id,
                            'respuesta_texto': texto
                        }
                    )

            # --- RECALCULAR NOTA ---
            # Llamamos a la función inteligente que creamos arriba
            # --- ¡AQUÍ SE LLAMA AL CEREBRO! ---
            # Esto calcula la nota inicial (las de texto valdrán 0 hasta que corrijas)
            recalcular_nota_examen(user, examen_obj) 
            
            # Marcar como Finalizado
            estado_obj, _ = EstadoExamen.objects.get_or_create(user=user, id_examen=examen_id)
            estado_obj.estado = 'F'
            estado_obj.save()
            
            # Limpieza de sesión
            if session_key in request.session:
                del request.session[session_key]

            return JsonResponse({'status': 'success', 'message': 'Examen guardado correctamente.'})
        
        except Exception as e:
            print(f"Error en submit_exam: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)




@never_cache
@login_required
def get_exam_review(request, examen_id):
    if request.method == "GET":
        try:
            # Obtener todas las preguntas del examen
            preguntas = PreguntasExamen.objects.filter(id_examen_id=examen_id).order_by('id_preguntas_examen')
            
            # Obtener las respuestas de este usuario para este examen
            user_answers = RespuestasUsuario.objects.filter(user=request.user, id_examen_id=examen_id)
            # Convertir a un diccionario para búsqueda rápida: {id_pregunta: id_alternativa_marcada}
            user_answers_map = {ans.id_preguntas_examen_id: ans.id_alternativas_examen_id for ans in user_answers}

            review_data = []
            
            for pregunta in preguntas:
                alternativas_data = []
                
                # Obtener todas las alternativas para esta pregunta
                alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)
                
                for alt in alternativas:
                    alternativas_data.append({
                        'id': alt.id_alternativas_examen,
                        'texto': alt.texto_alternativa,
                        'es_correcta': alt.valor == 'C',
                        'marcada_por_usuario': user_answers_map.get(pregunta.id_preguntas_examen) == alt.id_alternativas_examen
                    })
                
                review_data.append({
                    'pregunta_texto': pregunta.texto_pregunta,
                    'alternativas': alternativas_data
                })

            return JsonResponse({'status': 'success', 'review': review_data})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)
    

def professor_required(function=None, redirect_field_name=None, login_url='signin'):
    """
    Decorador para vistas que comprueba que el usuario sea staff (profesor).
    """
    actual_decorator = user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if function:
        return actual_decorator(function)
    return actual_decorator



# --- VISTA PARA ASIGNAR ALUMNOS (EJEMPLO DE LÓGICA) ---



# --- CRUD CURSOS ---

@login_required
@professor_required
#def professor_dashboard(request):
#    """
#    Panel principal del profesor. Muestra los cursos que le pertenecen.
#    """
#    cursos = Cursos.objects.filter(id_profesor=request.user)
#    context = {
#        'lista_cursos': cursos
#    }
#    return render(request, 'profesor/professor_dashboard.html', context)


def professor_dashboard(request):
    # Solo traer los salones donde el profesor asignado sea el usuario actual
    mis_salones = Salon.objects.filter(id_profesor=request.user)
    return render(request, 'professor_dashboard.html', {'salones': mis_salones})

@login_required
@professor_required
def professor_manage_course(request, curso_id):
    """
    Panel para gestionar un curso. Muestra los exámenes de ESE curso.
    """
    # QUITAMOS la búsqueda de profesor en el curso (el curso es universal)
    curso = get_object_or_404(Cursos, id_cursos=curso_id) 
    
    # AGREGAMOS la búsqueda de profesor directamente en el Examen
    examenes = Examen.objects.filter(id_curso=curso, id_profesor=request.user)
    
    context = {
        'curso': curso,
        'lista_examenes': examenes
    }
    return render(request, 'profesor/professor_manage_course.html', context)

# --- CRUD EXÁMENES ---

@login_required
@professor_required
def professor_create_exam(request, curso_id):
    """
    Vista para crear un nuevo examen DENTRO de un curso.
    """
    # QUITAMOS la validación del profesor aquí
    curso = get_object_or_404(Cursos, id_cursos=curso_id) 
    if request.method == 'POST':
        form = ExamenForm(request.POST)
        if form.is_valid():
            examen = form.save(commit=False)
            examen.id_curso = curso 
            
            # --- ¡LA MAGIA OCURRE AQUÍ! ---
            # Guardamos al profesor actual como el AUTOR del examen
            examen.id_profesor = request.user 
            
            examen.save()
            messages.success(request, 'Examen creado exitosamente.')
            return redirect('professor_manage_course', curso_id=curso.id_cursos)
    else:
        form = ExamenForm()
    
    return render(request, 'profesor/professor_exam_form.html', {'form': form, 'titulo': f'Crear Examen para {curso.nombre_curso}'})



@login_required
@professor_required
def professor_edit_exam(request, examen_id):
    """
    Vista para editar el título de un examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    if request.method == 'POST':
        form = ExamenForm(request.POST, instance=examen)
        if form.is_valid():
            form.save()
            messages.success(request, 'Examen actualizado exitosamente.')
            return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)
    else:
        form = ExamenForm(instance=examen)
    
    return render(request, 'profesor/professor_exam_form.html', {'form': form, 'titulo': f'Editar: {examen.titulo}'})

@login_required
@professor_required
def professor_delete_exam(request, examen_id):
    """
    Vista para eliminar un examen (Confirmación).
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    curso_id = examen.id_curso.id_cursos # Guardamos el ID antes de borrar
    if request.method == 'POST':
        examen.delete()
        messages.success(request, 'Examen eliminado exitosamente.')
        return redirect('professor_manage_course', curso_id=curso_id)
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': examen})





# En tasks/views.py
# (Asegúrate de tener importado 'User' de django.contrib.auth.models)

@login_required
@professor_required
def professor_assign_students(request, examen_id):
    """
    Vista MEJORADA para asignar/desasignar Y gestionar el estado por alumno.
    Incluye lógica para mostrar NOTAS.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    all_students = User.objects.filter(is_staff=False, is_superuser=False).order_by('username')
    
    # Obtenemos las asignaciones existentes
    existing_assignments = EstadoExamen.objects.filter(id_examen=examen)
    
    # Mapeamos por ID de usuario -> Objeto EstadoExamen completo
    assignment_map = {asig.user_id: asig for asig in existing_assignments}

    if request.method == 'POST':
        try:
            assigned_student_ids = request.POST.getlist('assigned_students')
            
            to_create = []
            to_update = []
            ids_to_delete = []

            with transaction.atomic():
                for student in all_students:
                    student_id_str = str(student.id)
                    
                    # Obtenemos el objeto asignación (si existe) y su estado actual (texto)
                    assignment_obj = assignment_map.get(student.id)
                    current_status_str = assignment_obj.estado if assignment_obj else None
                    
                    is_checked = student_id_str in assigned_student_ids
                    
                    if is_checked:
                        new_status = request.POST.get(f'status_{student_id_str}', 'A')
                        
                        if assignment_obj is None:
                            # Crear nuevo
                            to_create.append(EstadoExamen(user=student, id_examen=examen, estado=new_status))
                        elif current_status_str != new_status:
                            # Actualizar existente
                            assignment_obj.estado = new_status
                            to_update.append(assignment_obj)
                    else:
                        # Si se desmarca y existía, borrar
                        if assignment_obj is not None:
                            ids_to_delete.append(student.id)

                if ids_to_delete:
                    EstadoExamen.objects.filter(id_examen=examen, user_id__in=ids_to_delete).delete()
                if to_create:
                    EstadoExamen.objects.bulk_create(to_create)
                if to_update:
                    EstadoExamen.objects.bulk_update(to_update, ['estado'])

            messages.success(request, 'Asignaciones actualizadas correctamente.')
            return redirect('professor_assign_students', examen_id=examen_id)

        except Exception as e:
            print(f"Error en asignación: {e}")
            messages.error(request, "Error al guardar cambios.")

    # Preparar datos para la plantilla (GET)
    student_data = []
    for student in all_students:
        assignment_obj = assignment_map.get(student.id)
        
        student_data.append({
            'student': student,
            'is_assigned': assignment_obj is not None,
            # Si existe objeto, usamos su estado y su nota. Si no, valores por defecto.
            'status': assignment_obj.estado if assignment_obj else 'A',
            'nota': assignment_obj.nota if assignment_obj else None 
        })

    context = {
        'examen': examen,
        'student_data': student_data
    }
    return render(request, 'profesor/professor_assign_students.html', context)


###detalle examen
# tasks/views.py

@login_required
@professor_required
def professor_review_exam(request, examen_id, alumno_id):
    """
    Permite al profesor ver el detalle del examen resuelto por un alumno específico.
    CORREGIDO: Maneja preguntas abiertas y evita el error de atributo.
    """
    # 1. Seguridad y Datos Básicos
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    alumno = get_object_or_404(User, id=alumno_id)
    estado_examen = get_object_or_404(EstadoExamen, user=alumno, id_examen=examen)

    # 2. Obtener preguntas que respondió el alumno (o se le asignaron)
    ids_respondidos = RespuestasUsuario.objects.filter(
        user=alumno, 
        id_examen=examen
    ).values_list('id_preguntas_examen', flat=True)

    preguntas = PreguntasExamen.objects.filter(
        id_preguntas_examen__in=ids_respondidos
    )
    
    resultados = []
    for pregunta in preguntas:
        alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)
        
        respuesta_usuario = RespuestasUsuario.objects.filter(
            user=alumno,              
            id_preguntas_examen=pregunta     
        ).first()
        
        # --- INICIO DE LA CORRECCIÓN ---
        alternativa_seleccionada_id = None
        texto_respuesta = None
        puntaje_obtenido = 0
        respuesta_id = None
        comentario = ""

        if respuesta_usuario:
            # A. Si es de Marcar: Sacamos el ID de la alternativa (Solo si existe)
            if respuesta_usuario.id_alternativas_examen:
                alternativa_seleccionada_id = respuesta_usuario.id_alternativas_examen.pk
            
            # B. Si es Abierta o para mostrar feedback: Sacamos los otros datos
            texto_respuesta = respuesta_usuario.respuesta_texto
            puntaje_obtenido = respuesta_usuario.puntaje_obtenido
            respuesta_id = respuesta_usuario.pk
            comentario = respuesta_usuario.comentario_profesor
        # --------------------------------
        
        resultados.append({
            'pregunta': pregunta,
            'alternativas': alternativas,
            'seleccionada_id': alternativa_seleccionada_id,
            # Pasamos los datos nuevos a la plantilla
            'respuesta_texto': texto_respuesta,
            'puntaje_obtenido': puntaje_obtenido,
            'respuesta_id': respuesta_id,
            'comentario': comentario,
        })

    context = {
        'examen': examen,
        'alumno': alumno,
        'resultados': resultados,
        'nota': estado_examen.nota
    }
    return render(request, 'profesor/professor_review_exam.html', context)








# ... (después de 'professor_assign_students') ...

@login_required
@professor_required
def professor_set_exam_status(request, examen_id, status):
    """
    Vista para BLOQUEAR ('D') o ACTIVAR ('A') un examen para todos
    los alumnos que ya lo tienen asignado.
    """
    # Verificamos que el profesor sea dueño del examen
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    
    # Solo permitimos cambiar a 'A' o 'D'
    if status not in ['A', 'D']:
        messages.error(request, "Estado no válido.")
        return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)

    # Actualizamos el estado SOLO de los exámenes 'Activos' o 'Deshabilitados'.
    # No queremos "activar" un examen que un alumno ya 'Finalizó' ('F').
    rows_affected = EstadoExamen.objects.filter(
        id_examen=examen,
        estado__in=['A', 'D']  # Solo afecta a los no finalizados
    ).update(estado=status)
    
    action_text = "activado" if status == 'A' else "bloqueado"
    messages.success(request, f"Examen {action_text} para {rows_affected} alumnos.")
    
    return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)



# --- CRUD PREGUNTAS ---

@login_required
@professor_required
def professor_manage_questions(request, examen_id):
    """
    Muestra la lista de preguntas de un examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    preguntas = PreguntasExamen.objects.filter(id_examen=examen)
    context = {
        'examen': examen,
        'lista_preguntas': preguntas
    }
    return render(request, 'profesor/professor_manage_questions.html', context)

@login_required
@professor_required
def professor_create_question(request, examen_id):
    """
    Crea una nueva pregunta para un examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    if request.method == 'POST':
        form = PreguntaForm(request.POST)
        if form.is_valid():
            pregunta = form.save(commit=False)
            pregunta.id_examen = examen
            pregunta.save()
            messages.success(request, 'Pregunta creada. Ahora añade las alternativas.')
            return redirect('professor_manage_alternatives', pregunta_id=pregunta.id_preguntas_examen)
    else:
        form = PreguntaForm()
    
    return render(request, 'profesor/professor_question_form.html', {'form': form, 'titulo': f'Nueva Pregunta para {examen.titulo}'})

@login_required
@professor_required
def professor_edit_question(request, pregunta_id):
    """
    Edita el texto de una pregunta.
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_profesor=request.user)
    if request.method == 'POST':
        form = PreguntaForm(request.POST, instance=pregunta)
        if form.is_valid():
            form.save()
            messages.success(request, 'Pregunta actualizada.')
            return redirect('professor_manage_questions', examen_id=pregunta.id_examen.id_examen)
    else:
        form = PreguntaForm(instance=pregunta)
    
    return render(request, 'profesor/professor_question_form.html', {'form': form, 'titulo': 'Editar Pregunta'})

@login_required
@professor_required
def professor_delete_question(request, pregunta_id):
    """
    Elimina una pregunta (Confirmación).
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_profesor=request.user)
    examen_id = pregunta.id_examen.id_examen
    if request.method == 'POST':
        pregunta.delete()
        messages.success(request, 'Pregunta eliminada.')
        return redirect('professor_manage_questions', examen_id=examen_id)
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': pregunta})


# --- CRUD ALTERNATIVAS ---

@login_required
@professor_required
def professor_manage_alternatives(request, pregunta_id):
    """
    Muestra la lista de alternativas de una pregunta.
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_profesor=request.user)
    alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)
    context = {
        'pregunta': pregunta,
        'lista_alternativas': alternativas
    }
    return render(request, 'profesor/professor_manage_alternatives.html', context)

@login_required
@professor_required
def professor_create_alternative(request, pregunta_id):
    """
    Crea una nueva alternativa para una pregunta.
    """
    pregunta = get_object_or_404(PreguntasExamen, id_preguntas_examen=pregunta_id, id_examen__id_profesor=request.user)
    if request.method == 'POST':
        form = AlternativaForm(request.POST)
        if form.is_valid():
            alternativa = form.save(commit=False)
            alternativa.id_preguntas_examen = pregunta
            alternativa.save()
            messages.success(request, 'Alternativa guardada.')
            return redirect('professor_manage_alternatives', pregunta_id=pregunta.id_preguntas_examen)
    else:
        form = AlternativaForm()
    
    return render(request, 'profesor/professor_alternative_form.html', {'form': form, 'titulo': f'Nueva Alternativa para: "{pregunta.texto_pregunta}"'})

# tasks/views.py



@login_required
@professor_required
def professor_edit_alternative(request, alternativa_id):
    """
    Edita una alternativa y RECALCULA las notas de todos los alumnos
    si la respuesta correcta cambió.
    """
    alternativa = get_object_or_404(
        AlternativasExamen, 
        id_alternativas_examen=alternativa_id, 
        id_preguntas_examen__id_examen__id_profesor=request.user
    )

    if request.method == 'POST':
        form = AlternativaForm(request.POST, instance=alternativa)
        if form.is_valid():
            alternativa_guardada = form.save()
            
            # --- LÓGICA DE ACTUALIZACIÓN MASIVA ---
            # 1. Identificar el examen
            pregunta = alternativa_guardada.id_preguntas_examen
            examen = pregunta.id_examen
            
            # 2. Buscar alumnos que ya finalizaron este examen
            estados_finalizados = EstadoExamen.objects.filter(id_examen=examen, estado='F')
            
            # 3. Recalcular la nota para cada uno
            contador_actualizados = 0
            for estado in estados_finalizados:
                recalcular_nota_examen(estado.user, examen)
                contador_actualizados += 1
            
            # --------------------------------------

            msg_extra = f" y se recalcularon {contador_actualizados} notas." if contador_actualizados > 0 else "."
            messages.success(request, f'Alternativa actualizada{msg_extra}')
            
            return redirect('professor_manage_alternatives', pregunta_id=pregunta.id_preguntas_examen)
    else:
        form = AlternativaForm(instance=alternativa)
    
    return render(request, 'profesor/professor_alternative_form.html', {'form': form, 'titulo': 'Editar Alternativa'})





@login_required
@professor_required
def professor_delete_alternative(request, alternativa_id):
    """
    Elimina una alternativa (Confirmación).
    """
    alternativa = get_object_or_404(AlternativasExamen, id_alternativas_examen=alternativa_id, id_preguntas_examen__id_examen__id_profesor=request.user)
    pregunta_id = alternativa.id_preguntas_examen.id_preguntas_examen
    if request.method == 'POST':
        alternativa.delete()
        messages.success(request, 'Alternativa eliminada.')
        return redirect('professor_manage_alternatives', pregunta_id=pregunta_id)
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': alternativa})



# ... (cerca de tus otras vistas de profesor) ...
@login_required
@professor_required
def professor_toggle_exam_visibility(request, examen_id):
    """
    Vista para cambiar el estado 'is_visible' de un Examen.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    
    # Cambia el valor booleano
    examen.is_visible = not examen.is_visible
    examen.save()
    
    action_text = "visible" if examen.is_visible else "invisible"
    messages.success(request, f"Examen '{examen.titulo}' ahora está {action_text} para todos los alumnos.")
    
    return redirect('professor_manage_course', curso_id=examen.id_curso.id_cursos)








#######################SALONESSSSSSSSSSSSS########################3

# En tasks/views.py

@login_required
@professor_required
def professor_manage_exam_salons(request, examen_id):
    """
    Muestra la lista de salones asociados al CURSO de este examen.
    El profesor elige un salón para gestionar sus asignaciones.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    
    # Obtenemos los salones que pertenecen al MISMO CURSO del examen
    # y que son gestionados por este profesor (seguridad extra)
    salones = Salon.objects.filter(
        id_curso=examen.id_curso,
        id_profesor=request.user
    )
    
    context = {
        'examen': examen,
        'salones': salones
    }
    return render(request, 'profesor/professor_manage_exam_salons.html', context)


@login_required
@professor_required
def professor_assign_students_to_exam_in_salon(request, examen_id, salon_id):
    """
    Gestiona la asignación para un SALÓN específico.
    AHORA INCLUYE NOTAS Y BOTÓN DE REVISIÓN.
    """
    examen = get_object_or_404(Examen, id_examen=examen_id, id_profesor=request.user)
    salon = get_object_or_404(Salon, id_salon=salon_id, id_curso=examen.id_curso)
    
    # 1. Alumnos del salón
    alumnos_salon = salon.alumnos.all().order_by('username')
    
    # 2. Asignaciones existentes (Guardamos el objeto completo para tener la nota)
    existing_assignments = EstadoExamen.objects.filter(id_examen=examen)
    assignment_map = {asig.user_id: asig for asig in existing_assignments} 

    if request.method == 'POST':
        try:
            assigned_student_ids = request.POST.getlist('assigned_students')
            to_create = []
            to_update = []
            ids_to_delete = []

            with transaction.atomic():
                for student in alumnos_salon:
                    student_id_str = str(student.id)
                    assignment_obj = assignment_map.get(student.id)
                    current_status = assignment_obj.estado if assignment_obj else None
                    
                    is_checked = student_id_str in assigned_student_ids
                    
                    if is_checked:
                        new_status = request.POST.get(f'status_{student_id_str}', 'A')
                        
                        if assignment_obj is None:
                            to_create.append(EstadoExamen(user=student, id_examen=examen, estado=new_status))
                        elif current_status != new_status:
                            assignment_obj.estado = new_status
                            to_update.append(assignment_obj)
                    else:
                        if assignment_obj is not None:
                            ids_to_delete.append(student.id)

                if ids_to_delete:
                    EstadoExamen.objects.filter(id_examen=examen, user_id__in=ids_to_delete).delete()
                if to_create:
                    EstadoExamen.objects.bulk_create(to_create)
                if to_update:
                    EstadoExamen.objects.bulk_update(to_update, ['estado'])

            messages.success(request, f'Asignaciones actualizadas para {salon.nombre_salon}.')
            return redirect('professor_assign_students_to_exam_in_salon', examen_id=examen.id_examen, salon_id=salon.id_salon)

        except Exception as e:
            print(f"Error: {e}")
            messages.error(request, "Ocurrió un error al guardar.")

    # 3. Preparar datos (INCLUYENDO LA NOTA)
    student_data = []
    for student in alumnos_salon:
        assignment_obj = assignment_map.get(student.id)
        student_data.append({
            'student': student,
            'is_assigned': assignment_obj is not None,
            'status': assignment_obj.estado if assignment_obj else 'A',
            'nota': assignment_obj.nota if assignment_obj else None # <--- ¡AQUÍ ESTÁ LA CLAVE!
        })

    context = {
        'examen': examen,
        'salon': salon,
        'student_data': student_data
    }
    return render(request, 'profesor/professor_assign_students_to_exam_in_salon.html', context)





# tasks/views.py

@login_required
def ver_resultados_examen(request, examen_id):
    examen = get_object_or_404(Examen, id_examen=examen_id)
    
    # Validar que el examen ya esté finalizado
    estado = get_object_or_404(EstadoExamen, user=request.user, id_examen=examen)
    if estado.estado != 'F':
        return redirect('exam_dashboard')

    # =========================================================
    # --- 1. LÓGICA DE SEGURIDAD: PEDIR CONTRASEÑA DEL ALUMNO ---
    # =========================================================
    session_key = f'resultados_desbloqueados_{examen_id}_{request.user.id}'
    
    # Si envía el formulario con la contraseña...
    if request.method == 'POST':
        password_ingresada = request.POST.get('password', '')
        
        # Comparamos con su contraseña real de la base de datos
        if request.user.check_password(password_ingresada):
            request.session[session_key] = True # ¡Desbloqueado!
            return redirect('ver_resultados_examen', examen_id=examen.id_examen)
        else:
            messages.error(request, 'Contraseña incorrecta. Por favor, intenta de nuevo.')

    # Si aún no ha desbloqueado los resultados, le mostramos la pantalla de candado
    if not request.session.get(session_key):
        return render(request, 'ver_resultados.html', {
            'examen': examen,
            'requiere_auth': True # Esta variable activa el candado en el HTML
        })
    # =========================================================


    # =========================================================
    # --- 2. LÓGICA NORMAL: CARGAR LOS RESULTADOS ---
    # =========================================================
    ids_respondidos = RespuestasUsuario.objects.filter(
        user=request.user, id_examen=examen
    ).values_list('id_preguntas_examen', flat=True)

    preguntas = PreguntasExamen.objects.filter(id_preguntas_examen__in=ids_respondidos)
    
    resultados = []
    for pregunta in preguntas:
        alternativas = AlternativasExamen.objects.filter(id_preguntas_examen=pregunta)
        respuesta_usuario = RespuestasUsuario.objects.filter(user=request.user, id_preguntas_examen=pregunta).first()
        
        seleccionada_id = None
        respuesta_texto = None
        puntaje_obtenido = 0
        comentario = ""

        if respuesta_usuario:
            if respuesta_usuario.id_alternativas_examen:
                seleccionada_id = respuesta_usuario.id_alternativas_examen.pk
            
            respuesta_texto = respuesta_usuario.respuesta_texto
            puntaje_obtenido = respuesta_usuario.puntaje_obtenido
            comentario = respuesta_usuario.comentario_profesor

        resultados.append({
            'pregunta': pregunta,
            'alternativas': alternativas,
            'seleccionada_id': seleccionada_id,
            'respuesta_texto': respuesta_texto,
            'puntaje_obtenido': puntaje_obtenido,
            'comentario': comentario 
        })

    context = {
        'examen': examen,
        'resultados': resultados,
        'nota': estado.nota
    }
    return render(request, 'ver_resultados.html', context)


# --- CRUD SALONES ---

@login_required
@professor_required
def professor_manage_salons(request):
    """
    Lista todos los salones que pertenecen al profesor actual.
    """
    # SEGURIDAD: Filtramos solo por el usuario logueado
    salones = Salon.objects.filter(id_profesor=request.user).select_related('id_curso')
    context = {
        'lista_salones': salones
    }
    return render(request, 'profesor/professor_manage_salons.html', context)

@login_required
@professor_required
def professor_create_salon(request):
    """
    Crea un nuevo salón asignado al profesor actual.
    """
    if request.method == 'POST':
        # Pasamos 'request.user' al form para filtrar los cursos
        form = SalonForm(request.user, request.POST)
        if form.is_valid():
            salon = form.save(commit=False)
            salon.id_profesor = request.user  # Asignamos dueño automáticamente
            salon.save()
            messages.success(request, 'Salón creado exitosamente.')
            return redirect('professor_manage_salons')
    else:
        form = SalonForm(request.user)
    
    return render(request, 'profesor/professor_salon_form.html', {'form': form, 'titulo': 'Crear Nuevo Salón'})

@login_required
@professor_required
def professor_edit_salon(request, salon_id):
    """
    Edita un salón existente. Solo si pertenece al profesor.
    """
    # SEGURIDAD: Si el salón es de otro profe, dará error 404
    salon = get_object_or_404(Salon, id_salon=salon_id, id_profesor=request.user)
    
    if request.method == 'POST':
        form = SalonForm(request.user, request.POST, instance=salon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Salón actualizado exitosamente.')
            return redirect('professor_manage_salons')
    else:
        form = SalonForm(request.user, instance=salon)
    
    return render(request, 'profesor/professor_salon_form.html', {'form': form, 'titulo': f'Editar: {salon.nombre_salon}'})

@login_required
@professor_required
def professor_delete_salon(request, salon_id):
    """
    Elimina un salón. Solo si pertenece al profesor.
    """
    salon = get_object_or_404(Salon, id_salon=salon_id, id_profesor=request.user)
    
    if request.method == 'POST':
        salon.delete()
        messages.success(request, 'Salón eliminado exitosamente.')
        return redirect('professor_manage_salons')
    
    return render(request, 'profesor/confirm_delete.html', {'objeto': salon})



@login_required
@professor_required
def professor_manage_salon_students(request, salon_id):
    """
    Permite al profesor añadir o quitar alumnos de un salón específico.
    """
    # 1. Obtener el salón y verificar que pertenece al profesor
    salon = get_object_or_404(Salon, id_salon=salon_id, id_profesor=request.user)

    # 2. Obtener TODOS los alumnos registrados en el sistema (no staff)
    all_students = User.objects.filter(is_staff=False, is_superuser=False).order_by('username')

    # 3. Obtener los IDs de los alumnos que YA están en este salón
    current_student_ids = set(salon.alumnos.values_list('id', flat=True))

    if request.method == 'POST':
        # Obtener lista de IDs seleccionados en el formulario
        selected_ids = request.POST.getlist('students')
        selected_ids = [int(id) for id in selected_ids] # Convertir a enteros

        # Calcular quiénes entran y quiénes salen
        ids_to_add = set(selected_ids) - current_student_ids
        ids_to_remove = current_student_ids - set(selected_ids)

        with transaction.atomic():
            # Agregar nuevos
            if ids_to_add:
                new_relations = [
                    SalonAlumnos(id_salon=salon, id_alumno_id=uid)
                    for uid in ids_to_add
                ]
                SalonAlumnos.objects.bulk_create(new_relations)
            
            # Eliminar los desmarcados
            if ids_to_remove:
                SalonAlumnos.objects.filter(
                    id_salon=salon, 
                    id_alumno_id__in=ids_to_remove
                ).delete()

        messages.success(request, f'Lista de alumnos actualizada para el salón {salon.nombre_salon}.')
        return redirect('professor_manage_salon_students', salon_id=salon.id_salon)

    # Preparar datos para la plantilla (marcar los que ya están)
    student_list = []
    for student in all_students:
        student_list.append({
            'user': student,
            'is_in_salon': student.id in current_student_ids
        })

    context = {
        'salon': salon,
        'student_list': student_list
    }
    return render(request, 'profesor/professor_manage_salon_students.html', context)



###########excel################33
def descargar_plantilla_excel(request):
    # Definimos dos ejemplos para que el profesor entienda cómo llenar
    data = {
        'Pregunta': [
            '¿Cuál es la capital de Perú? (Ejemplo Múltiple)', 
            'Describa brevemente el ciclo del agua (Ejemplo Abierta)'
        ],
        'Tipo': [
            'M',  # M = Múltiple (Automática)
            'A'   # A = Abierta (Manual)
        ],
        'Puntaje': [
            1.0,  # Vale 1 punto
            4.0   # Vale 4 puntos (es más difícil)
        ],
        'Opcion_1': [
            'Lima', 
            '' # Vacío en la abierta
        ],
        'Valor_1': [
            'C', # C = Correcta
            ''
        ],
        'Opcion_2': [
            'Arequipa', 
            ''
        ],
        'Valor_2': [
            'I', # I = Incorrecta
            ''
        ],
        'Opcion_3': [
            'Trujillo', 
            ''
        ],
        'Valor_3': [
            'I',
            ''
        ],
        'Opcion_4': [
            'Cusco', 
            ''
        ],
        'Valor_4': [
            'I',
            ''
        ],
    }
    
    # Creamos el DataFrame
    df = pd.DataFrame(data)
    
    # Preparamos la respuesta HTTP para descargar el archivo
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=plantilla_examen_v2.xlsx'
    
    # Guardamos usando openpyxl
    df.to_excel(response, index=False, engine='openpyxl')
    
    return response

######plantilla excel


def subir_preguntas_excel(request, examen_id):
    if request.method == 'POST' and request.FILES['archivo_excel']:
        archivo = request.FILES['archivo_excel']
        
        try:
            # --- DETECCIÓN DE FORMATO ---
            if archivo.name.endswith('.csv'):
                df = pd.read_csv(archivo, encoding='utf-8-sig').fillna('')
            else:
                df = pd.read_excel(archivo).fillna('')
            
            # --- 1. VALIDACIÓN DEL FORMATO ---
            if 'Pregunta' not in df.columns:
                messages.error(request, "Error: El archivo no tiene la columna obligatoria 'Pregunta'.")
                return redirect('professor_manage_questions', examen_id=examen_id)

            # --- 2. DETECCIÓN DE COLUMNAS DE OPCIONES ---
            columnas_opciones = [col for col in df.columns if col.startswith('Opcion_')]
            
            indices_encontrados = []
            for col in columnas_opciones:
                partes = col.split('_')
                if len(partes) > 1 and partes[1].isdigit():
                    indices_encontrados.append(int(partes[1]))
            indices_encontrados.sort()

            # --- 3. PROCESAMIENTO ---
            with transaction.atomic():
                contador_preguntas = 0
                examen = Examen.objects.get(id_examen=examen_id)

                for index, row in df.iterrows():
                    texto_pregunta = str(row['Pregunta']).strip()
                    if not texto_pregunta: continue 

                    # A) LEER TIPO (Por defecto 'M' si no existe la columna)
                    tipo_leido = 'M'
                    if 'Tipo' in df.columns:
                        val_tipo = str(row['Tipo']).strip().upper()
                        # Aceptamos 'A' o 'ABIERTA', 'M' o 'MULTIPLE'
                        if val_tipo.startswith('A'):
                            tipo_leido = 'A'
                        else:
                            tipo_leido = 'M'
                    
                    # B) LEER PUNTAJE (Por defecto 1.0 si no existe)
                    puntaje_leido = 1.0
                    if 'Puntaje' in df.columns:
                        try:
                            val_puntaje = float(str(row['Puntaje']).replace(',', '.'))
                            puntaje_leido = val_puntaje
                        except:
                            puntaje_leido = 1.0

                    # C) CREAR PREGUNTA
                    nueva_pregunta = PreguntasExamen.objects.create(
                        id_examen=examen,
                        texto_pregunta=texto_pregunta,
                        tipo_pregunta=tipo_leido,      # <--- Asignamos el tipo
                        puntaje_maximo=puntaje_leido   # <--- Asignamos el puntaje
                    )
                    contador_preguntas += 1

                    # D) CREAR ALTERNATIVAS (SOLO SI ES TIPO 'M')
                    if tipo_leido == 'M':
                        for i in indices_encontrados:
                            col_opcion = f'Opcion_{i}'
                            col_valor = f'Valor_{i}'
                            
                            # Verificamos que la columna exista en el row
                            opcion_texto = str(row.get(col_opcion, '')).strip()
                            opcion_valor = str(row.get(col_valor, 'I')).strip().upper()

                            if opcion_texto and opcion_texto.lower() != 'nan':
                                AlternativasExamen.objects.create(
                                    id_preguntas_examen=nueva_pregunta,
                                    texto_alternativa=opcion_texto,
                                    valor=opcion_valor
                                )
                
                if contador_preguntas > 0:
                    messages.success(request, f'¡Éxito! Se importaron {contador_preguntas} preguntas.')
                else:
                    messages.warning(request, 'El archivo no contenía preguntas válidas.')
        
        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            
    return redirect('professor_manage_questions', examen_id=examen_id)







# tasks/views.py

# tasks/views.py

def recalcular_nota_examen(user, examen):
    """
    Calcula la nota real sumando puntajes automáticos y manuales.
    Actualiza la tabla EstadoExamen.
    """
    # 1. Traer todas las respuestas del alumno
    respuestas = RespuestasUsuario.objects.filter(user=user, id_examen=examen).select_related('id_preguntas_examen', 'id_alternativas_examen')
    
    total_puntos_obtenidos = 0
    total_puntos_posibles = 0 # La suma de lo que valen las preguntas que le tocaron
    
    for resp in respuestas:
        pregunta = resp.id_preguntas_examen
        total_puntos_posibles += pregunta.puntaje_maximo
        
        # --- LÓGICA MIXTA ---
        if pregunta.tipo_pregunta == 'M': 
            # CASO A: Marcar (Automático)
            # Si marcó algo Y es la correcta ('C'), gana el puntaje máximo de esa pregunta
            if resp.id_alternativas_examen and resp.id_alternativas_examen.valor == 'C':
                resp.puntaje_obtenido = pregunta.puntaje_maximo
            else:
                resp.puntaje_obtenido = 0
            resp.save() # Guardamos el cálculo individual
            
        elif pregunta.tipo_pregunta == 'A':
            # CASO B: Abierta (Manual)
            # Aquí NO tocamos el puntaje, usamos el que el profesor ya puso (o 0 si no ha corregido)
            pass 
            
        total_puntos_obtenidos += resp.puntaje_obtenido

    # 2. Cálculo final (Escala vigesimal 0-20)
    if total_puntos_posibles > 0:
        # Regla de tres simple
        nota_final = (total_puntos_obtenidos * 20) / total_puntos_posibles
    else:
        nota_final = 0

    # 3. Guardar en EstadoExamen
    estado, created = EstadoExamen.objects.get_or_create(user=user, id_examen=examen)
    estado.nota = nota_final
    estado.save()
    
    return nota_final


# tasks/views.py

@login_required
@professor_required
def calificar_respuesta_ajax(request):
    """
    Recibe el puntaje manual del profesor para una pregunta abierta.
    """
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        respuesta_id = data.get('id_respuesta')
        puntaje_asignado = data.get('puntaje')
        
        try:
            resp = RespuestasUsuario.objects.get(id_respuesta=respuesta_id)
            maximo = resp.id_preguntas_examen.puntaje_maximo
            
            # Validar tope
            if float(puntaje_asignado) > float(maximo):
                return JsonResponse({'status': 'error', 'message': f'Máximo {maximo} puntos.'})
            
            resp.puntaje_obtenido = puntaje_asignado
            resp.save()
            
            # --- ¡RECALCULO AUTOMÁTICO! ---
            # Al guardar la nota manual, recalculamos el promedio final del alumno
            nueva_nota = recalcular_nota_examen(resp.user, resp.id_examen)
            
            return JsonResponse({'status': 'success', 'nueva_nota_total': nueva_nota})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
        

# Vista para reportar incidentes desde JS
# --- AGREGAR ANTES DE def submit_exam(request): ---

@csrf_exempt
@login_required
def reportar_incidencia(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            examen_id = data.get('examen_id')
            tipo = data.get('tipo')
            imagen_b64 = data.get('imagen') # La foto en base64
            
            # Decodificar imagen
            if imagen_b64:
                format, imgstr = imagen_b64.split(';base64,') 
                ext = format.split('/')[-1] 
                data_img = ContentFile(base64.b64decode(imgstr), name=f'{tipo}_{request.user.id}.{ext}')
            else:
                data_img = None
            
            IncidenciaExamen.objects.create(
                examen_id=examen_id,
                alumno=request.user,
                tipo=tipo,
                minuto_ocurrencia="En vivo",
                evidencia=data_img
            )
            print(f"INCIDENCIA REGISTRADA: {tipo} - Usuario {request.user.username}")
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            print(f"Error reportando incidencia: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})

@login_required
def get_user_reference_photo(request):
    """Devuelve la URL de la foto de referencia para que el JS compare"""
    try:
        perfil = PerfilBiometrico.objects.get(user=request.user)
        return JsonResponse({'status': 'ok', 'url': perfil.foto_referencia.url})
    except PerfilBiometrico.DoesNotExist:
        # Si no tiene foto, retornamos status especial para pedir que se tome una
        return JsonResponse({'status': 'no_photo'})
    


#VISTA DE RECONOCER FOTO Y GUARDAR FOTO DE LA PERSONA

# 1. VISTA DE ENROLAMIENTO (Página HTML)
@login_required
def enrolamiento_biometrico(request):
    # Si ya tiene foto, no debería estar aquí, lo mandamos al dashboard
    if PerfilBiometrico.objects.filter(user=request.user).exists():
        return redirect('exam_dashboard')
    
    # Si viene de un intento de examen, guardamos el ID para redirigirlo después
    next_exam = request.GET.get('next_exam')
    return render(request, 'enrolamiento.html', {'next_exam': next_exam})

# 2. API PARA GUARDAR LA FOTO (AJAX)
@login_required
@csrf_exempt # O usa el token en el fetch (recomendado usar token, aquí simplifico)
def guardar_foto_biometrica(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            imagen_b64 = data.get('imagen') # La foto en base64
            
            if not imagen_b64:
                return JsonResponse({'status': 'error', 'message': 'No se recibió imagen'})

            # Decodificar la imagen base64
            format, imgstr = imagen_b64.split(';base64,') 
            ext = format.split('/')[-1] 
            
            # Crear nombre de archivo único: "referencia_IDUSER.jpg"
            filename = f"referencia_{request.user.id}.{ext}"
            data_img = ContentFile(base64.b64decode(imgstr), name=filename)

            # Guardar o Actualizar
            perfil, created = PerfilBiometrico.objects.get_or_create(user=request.user)
            perfil.foto_referencia.save(filename, data_img)
            perfil.save()

            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

# 3. API PARA OBTENER LA URL DE LA FOTO (Para welcome_exam)
@login_required
def get_user_reference_photo(request):
    try:
        perfil = PerfilBiometrico.objects.get(user=request.user)
        if perfil.foto_referencia:
            return JsonResponse({'status': 'ok', 'url': perfil.foto_referencia.url})
    except PerfilBiometrico.DoesNotExist:
        pass
    return JsonResponse({'status': 'error', 'message': 'No existe perfil'})